---
name: kuraka-policies
description: "Cross-cutting Kuraka policies: retry, timeout, token budget, failure fallback, checkpointing, and telemetry. Applies in any mode."
disable-model-invocation: true
user-invocable: false
---

# Kuraka — Policies

Cross-cutting policies that apply in any Kuraka mode (Normal,
Reduced-by-risk, Lite, Retroactive).

---

## Agent Invocation Policy

Every `Agent` call has retry and timeout policies to prevent silent
failures from propagating through the workflow.

### Role lock (MANDATORY prompt preamble)

Every subagent invocation prompt begins with a role lock:

> You are a specialist subagent inside a running Kuraka cycle — the phase and
> the inputs in THIS prompt are your entire task. Do not read `kuraka.md` /
> `kuraka-modes.md`, do not invoke Kuraka skills or commands, do not spawn
> agents, do not propose a pipeline, do not ask what the requirement is. If an
> input artifact you need is missing, ask ONE precise question and stop.

Without it, a subagent can drift into acting as the orchestrator (guai
REQ-20260722: a Phase-2.5 invocation re-derived the whole pipeline and produced
nothing — 66K tokens; the explicit lock eliminated the confusion in later
cycles). *(Restored 2026-11 harvest: this section shipped in 1.1.0 and was lost
in an unrelated 2026-08-12 commit; 9 of 11 guai-home appends re-added it by hand.)*

### Git is READ-ONLY for review/verify subagents (HARD)

`architect-reviewer`, `code-reviewer`, `security-reviewer`, `test-engineer`
(review modes), `e2e-tester`, `deployment-verifier`, `migration-reviewer` — and
any agent whose job is to JUDGE work rather than produce it — may run only
read-only git: `status`, `log`, `diff`, `show`, `branch --list`, `rev-parse`,
`ls-files`, `merge-base`. They must NEVER run `merge`, `pull`, `checkout`,
`switch`, `reset`, `rebase`, `cherry-pick`, `stash`, `commit`, or `push`. A
dirty or mid-merge tree found on entry is a **BLOCKER to report, never a state
to resolve**. (guai REQ-20260721: a reviewer triggered an unintended `git merge`
mid-review and left the consumer branch in a conflicted state; kuraka-control
carried this as framework debt FD-16 through 8 cycles after the section was
lost.) Writes to the working tree belong to implementer agents and the
orchestrator only.

### Retry policy

- **Max 2 retries per agent** (3 total attempts).
- **Retry triggers**:
  - Malformed output (fails the `verify-output` schema).
  - Agent returned `VALIDATION_FAILED` marker.
  - Transient tool error (network, rate limit).
- **NO retry on**:
  - Error requiring user input (ask the user).
  - Deliberate agent rejection (e.g., "I can't proceed without X").
  - 3rd failure — escalate to the user.

### Retry protocol

On each retry, the orchestrator injects feedback into the next prompt:

```
PREVIOUS ATTEMPT FAILED VALIDATION
Issues found:
- {specific issue 1}
- {specific issue 2}

Please re-generate addressing these issues.
```

### Agent liveness — how to tell a working agent from a dead one

Before concluding that a long-running agent has died:

1. **Poll the files, not the clock.** `find <the agent's authorized paths>
   -newermt '-15 minutes'` and inspect the **MOST RECENTLY** modified file —
   never the first files it wrote. Early files go stale while the agent works
   normally, further down its own file list.
2. **`duration_ms` / wall-clock is NOT a health signal** (already policy for
   budget) and is **not evidence of death**.
3. **NEVER run a gate against a tree an agent still holds.** A mid-flight tree is
   *expected* to be red; reading that red as failure produces a false verdict on
   a healthy run.

Only after **≥ 2 polls, ≥ 10 minutes apart**, show zero modifications anywhere in
the authorized set should intervention be considered — and even then, snapshot
before gating.

**Evidence (REQ-20260801):** an agent was declared DEAD at ~7h on the stale
mtimes of its FIRST files, gated mid-flight, and its half-written state read as
failure. It was alive and finished green minutes later.

*(Claude Code: don't hand-poll — at Phase-4 start launch the streaming watcher
`bash .claude/hooks/liveness_watch.sh <authorized paths>` via the Monitor tool
or a background Bash task; activity lines = healthy. The manual protocol above
stays the DECISION rule for what silence means. For long L-size stories, prefer
launching the implementer as a background subagent and reacting to its
completion notification instead of waiting synchronously.)*

### Timeout policy

- **There is NO fixed wall-clock timeout.** Health is judged by the liveness
  protocol above (poll the authorized files, ≥ 2 polls ≥ 10 minutes apart) —
  never by duration. A healthy agent has run 7+ hours (REQ-20260801) while a
  duration-based rule would have killed it mid-flight.
- **Escalate to the user only when liveness fails** (zero file modifications
  across ≥ 2 spaced polls): "Agent {agent} shows no activity in its authorized
  paths for {N} min across {M} polls. Continue waiting, abort, or change
  strategy?" — and snapshot the tree before any intervention.
- **Long tasks are legitimate**; still prefer splitting stories into smaller
  units when the surface allows it (baby steps, Phase 4 rule).

### Failure fallback (3 failed attempts)

1. Write checkpoint with `status: "paused"` and failure details.
2. Report to the user:
   - Which agent failed.
   - What the 3 attempts produced.
   - Suggested next steps (manual retry, skip, human).
3. **WAIT for user decision** — don't auto-skip critical phases.

### Tool use limits per agent

To prevent runaway loops:

| Category | Max tool uses |
|---|---|
| Research (`po-analyst`, exploration) | 30 |
| Implementation (`backend-developer`, `frontend-developer`) | 50 |
| Review (`architect-reviewer`, `code-reviewer`, `security-reviewer`) | 40 |
| Audit (`final-auditor`, `pattern-detector`) | 25 |

If an agent exceeds its limit without producing output → treat as timeout.

**The harness turn ceiling is a hard wall, not a budget.** Implementer and test
agents run with `maxTurns` ≈ 100 (`AGENT-HARNESS.yaml`). An agent that hits it
ends **without a report** — the work it did is invisible and the phase must be
re-run (editorial: C06/C09 test runs with >12 acceptance criteria + mutations;
guai: one story needed 3 runs). So:

- **Size the batch to the ceiling.** A story that lists more than ~15 files or
  crosses more than 2 layers is split before Phase 4 (`story-refiner` /
  orchestrator); a test phase with >12 criteria + mutations is split by criterion.
- **The report is written incrementally from the first turn** (declared output
  path, appended as work lands), never composed only at the end.
- **At ~80 tool calls the agent stops expanding scope**: it runs its gate, writes
  the report with the explicit list of what remains, and hands back. A
  hand-back with a remaining-scope list is a success; a silent cut-off is not.
- **Resume prefers a fresh run + delta** (Rule T10: the remaining-scope list +
  the files already written) over re-loading the cut-off transcript, whose
  cumulative tokens re-buy the whole context.

**The tool-use cap is MEASURED after every invocation, exactly like the token cap.**
Advisory prose failed for the token cap until it became an action (see below); it is
failing for this one now. After each `Agent` call, compare `tool_uses` against the
agent's cap, at 0 tokens, and act:

| Consumption | Orchestrator action |
|---|---|
| **> 1.0×** | WARN + record `tool_uses_ok: false` + a `note` in telemetry |
| **> 2.0×** | WARN + **write the cause into the checkpoint** before the next invocation |
| **> 3.0×** | The agent must emit a check-in describing what it still needs **before** continuing |

Record `tool_uses_ok` alongside `budget_ok` in every telemetry entry.

**Evidence (REQ-20260804-audit-columns):** `story-refiner` ran **111/30 (3.7×)** and
`test-engineer` **100/50 (2.0×)** without a single warning, because `budget_ok` only
ever looked at tokens. The same cycle's token cap — an ACTION since REQ-20260801 —
caught and annotated all three over-budget analysis phases on the first try.

### Rate-limit policy during Phase 4

The orchestrator **MUST NOT** write implementation code under any
circumstances. If the implementer subagent (`backend-developer`,
`frontend-developer`, `test-engineer`) is rate-limited:

1. **First option** — `ScheduleWakeup` with delay based on estimated
   rate-limit duration:
   - Message "rate limited, retry in N minutes" →
     `ScheduleWakeup(delaySeconds=N*60+30, ...)` with a prompt that
     resumes the exact story.
2. **Second option** — degrade to an alternative agent: if the block is
   specific to one model, try `simplify` or a lower-cost agent for
   mechanical tasks (reduce scope to copy-paste with exact citations).
3. **Documented exception** — the orchestrator may write SOLELY in these
   cases, announcing first to the user:
   - Edits ≤ 5 LOC for a precise fix of a post-review IMPORTANT.
   - Mechanical refactor of an already-written migration (pattern change
     with no new logic).
   - **NEVER** a new file of > 50 LOC.

If the orchestrator writes code outside the exceptions, it must:
- Announce the violation to the user first.
- Request explicit approval.
- Trigger a mandatory re-review by the corresponding agent (same role,
  in a different invocation once the rate limit has passed).
- Document the violation in the Phase 7 RETRO.

**Why**: an orchestrator that implements directly normalizes a
role-isolation breakage that's hard to walk back from. Re-review can
mitigate the risk per case, but the pattern is dangerous if it becomes
routine.

---

## Gate command integrity (MANDATORY)

A gate result (test / lint / typecheck) counts only when the gate command ran
UNPIPED and the verdict cites **its own** exit code. See
`rules/17-kuraka-token-optimizations.md` Rule T7 for the full rule (dead
gates, isolated guard tests).

*(Claude Code: enforced by harness — the `gate_integrity` PreToolUse hook
blocks any Bash command that pipes a configured `test_cmd`/`lint_cmd`/
`typecheck_cmd`; user-approved exception: `KURAKA_GATE_PIPE_OK` marker in the
command.)*
<!-- kuraka:discipline:gate-integrity -->

---

## Definition of "green" (MANDATORY)

"Green" — the condition that lets a story or Phase 4 advance — means **lint +
typecheck + test ALL pass**, not just the test runner.

- Test runners that transpile per-file (vitest, jest, ts-jest) do **not**
  typecheck the dependency graph. A green test run can hide a `tsc --noEmit`
  error. If the stack defines a `typecheck_cmd` for a workspace, the story is
  not done until that command exits 0.
- Every agent's "tests green" claim must imply a clean typecheck. Prefer a
  single `make check` target (lint + typecheck + test) so the gate is one
  command that cannot pass while the build is broken.

- **The environment the gate runs in must be current.** A story that touches
  the dependency manifest, lockfile, or migrations forces a rebuild / recreate
  of the test image/containers BEFORE its gate is trusted (no-cache if
  migrations changed; compare the running image with the freshly built one);
  the gate never runs shadowed by host artifacts (e.g. a bind-mounted
  `node_modules`). A sudden burst of `Can't locate revision` / `column does not
  exist` after touching migrations is a false regression from a stale image —
  rebuild, don't chase (adela: two false greens in one cycle; guai: ~179 phantom
  failures; editorial LL-001). *(Restored 2026-11 harvest — 1.1.0 item P6, lost
  2026-08-12.)*
- **Green is bound to a commit.** A gate result is recorded with
  `gates_measured_at: <git rev-parse HEAD>` (and dirty-tree flag). A green
  measured at another HEAD — before the last fix-run, on another branch, or in
  another cycle's baseline — is not this story's green (guai FD-6, 5 cycles).
- **One test runner per host.** A gate (suite, mutation run, E2E) read while
  another suite / mutation / E2E is running on the same host is **void** — re-run
  it alone. A test that fails only under load is re-run **isolated 3×** before
  anyone calls it flaky; 3/3 green isolated + red under load = a real
  concurrency/timing finding, not noise (editorial F-15, 5 retros: LL-017/019/032).
- **Gate commands come from the project, never from an example.** The
  orchestrator and every agent read them from `kuraka.config.yaml`
  (`stack.*.test_cmd` / `lint_cmd` / `typecheck_cmd`) or the project's
  `conventions/gate-commands.md`; frontend scripts from
  `jq .scripts package.json`. If a workspace has no typecheck script, record the
  substitute actually run (e.g. `npx tsc --noEmit`) — never cite a command the
  project does not define. A config value of `TODO` / `TBD` / empty is **no
  gate** (report it, don't treat it as green).

Reference: kuraka-control LL-014 — an invalid `as string` cast rode green ~3
cycles because the Phase-4 gate ran vitest only. Also `gate command integrity`
above (the gate must be able to fail) and Phase 6.8 (`green ≠ working feature`).

---

## RTK token saver (transparent, if installed)

If RTK (`rtk`) is installed with its global hook (`rtk init -g` → a `PreToolUse`
hook `rtk hook claude` in `~/.claude/settings.json`), every Bash command an agent
runs is **automatically rewritten** to its filtered `rtk` form (grep/cat/ls/git/
test output is compressed before it reaches context). This needs NO per-agent
wiring — all Kuraka subagents inherit it. Typical savings 70–90% on dev ops; check
with `rtk gain`. See `RECOMMENDED-COMPONENTS.md`.

**One exception — bypass the filter for byte-exact reads.** RTK truncates/dedups
output, which can silently drop a field during a fidelity/contract check. When an
agent needs the *exact, full* bytes — a verbatim-payload diff, an in-vivo contract
probe, a frozen-schema cross-check, a count that is itself the evidence — run the
command through `rtk proxy <cmd>` (raw, unfiltered) instead of the rewritten form.
Never run a contract cross-check on truncated output.

---

## Token Budget (recommended)

Nominal budget per phase to detect deviations:

| Phase | Target | Investigate if exceeds |
|---|---:|---|
| 1 PO Analysis | 80–120K | 200K |
| 2 Story Refinement | 60–100K | 180K |
| 2.5 Test Planning | 60–100K | 150K |
| 3 Architect Review | 50–80K | 150K |
| 4a Backend Impl (per story M) | 100–200K | 400K |
| 4b Frontend Impl (per story M) | 100–200K | 400K |
| 5 Code Review | 70–120K | 200K |
| 5.5 Security Review | 60–100K | 180K |
| 6 Tests (per story M) | 80–150K | 300K |
| 6.5 E2E | 50–100K | 200K |
| 6.7 Deployment | 30–60K | 120K |
| 7 Final Audit | 40–80K | 150K |

### Size-aware thresholds (S / M / L)

The table above is the **M** row. A phase whose scope is declared S or L in the
prompt (story size from `story-refiner`; for analysis phases, the REQ size the
mode gate declared) is judged against its own band — one fixed number marks
every L cycle over budget and every S cycle as "fine" when it is not (petsuite:
phases 2/2.5/3 over the hard cap in 4 of 5 module cycles, `budget_ok` wrong in
both directions):

| Phase | S — investigate if exceeds | M | L |
|---|---:|---:|---:|
| 2 Story Refinement | 120K | 180K | 270K |
| 2.5 Test Planning | 100K | 150K | 225K |
| 3 Architect Review | 100K | 150K | 225K |
| 4a Backend Impl (per story) | 267K | 400K | 600K |
| 4b Frontend Impl (per story) | 267K | 400K | 600K |
| 6 Tests (per story) | 200K | 300K | 450K |

Rule of thumb: S = ⅔ × M, L = 1.5 × M. The size is **declared in the prompt
before the run** (`size: S|M|L`) and copied into the telemetry entry; a size
picked after seeing the tokens is not a size.

**Named variants** (declared in the prompt, copied into the entry as `variant`):

| Variant | Threshold |
|---|---|
| `1+2+2.5` — combined analysis run (Rule T3 default) | sum of the three phases' thresholds at the declared size (M: 530K) |
| `3+probe` — architect review with a declared empirical probe (running code / live DB) | 1.3 × the Phase-3 threshold (M: 195K) |

An undeclared variant is judged as the plain phase.

**`budget_ok` is computed, not typed.** `aggregate-telemetry.py` recomputes it
from `total_tokens`, `phase`, `size` and `variant` against these tables and flags
any entry whose hand-written `budget_ok` disagrees (guai: 11 false values in one
cycle). The value you write is a draft; the dashboard's is the verdict.

These thresholds are **tokens (model compute)** — the only real spend signal.
**Wall-clock `duration_ms` is NOT a budget gate**: it includes tool/DB/container
wait, so analysis phases and DB-bearing test-writing are legitimately slow without
overspending. A run that is slow but in-band on tokens is a latency artifact —
investigate it separately, never mark it over budget (guai: 7 cycles ran 31–86 min
yet reported `budget_ok: true`; the metric conflated wait with compute).

**Action if a phase exceeds "investigate if exceeds" (tokens)**:
1. Abort the phase if still running.
2. Analyze telemetry (which files were read? how many tool_uses?).
3. Apply patterns T1–T8 from `rules/17-kuraka-token-optimizations.md`.
4. Re-launch with an optimized prompt.

### The cap is an ACTION, measured after EVERY Agent call (MANDATORY)

Advisory text has failed for eight cycles. The orchestrator measures
`total_tokens` against the **phase** threshold after each invocation, at 0
tokens, and acts:

| Consumption | Orchestrator action |
|---|---|
| **> 1.0×** | WARN, write `budget_note`, continue |
| **> 1.5×** | WARN + **write the cause into the checkpoint** before the next invocation |
| **> 2.0×** | **HARD STOP.** Do not invoke the next phase until the digest or scope is re-cut, and the re-cut is written into the checkpoint |

Full rationale and evidence in `rules/17-kuraka-token-optimizations.md` → Rule T0.

### One budget model: PHASE thresholds win

`budget_ok` in the telemetry uses **per-phase** thresholds (this table). The
vault's `aggregate-telemetry.py` uses **per-agent** thresholds. They disagree —
REQ-20260801's Phase-2.5 run (291,085) is `budget_ok: false` against the 150K
phase threshold and simultaneously *in band* against the aggregator's 300K
test-engineer threshold, so it never appeared in the dashboard's over-budget
column. The same cycle reads as 4-over or 3-over depending on who you ask.

**Phase thresholds are authoritative**, because they encode what the phase
*should cost*, not what the agent *usually spends*. `aggregate-telemetry.py` must
be changed to read them; until it is, treat its over-budget column as a lower
bound.

### Telemetry completeness (REGRESSION — 3 consecutive cycles)

An `Agent` invocation with **no telemetry entry** is invisible to the audit, and
the cycle's reported cost is then wrong, not merely imprecise. REQ-20260801
recorded 19 of 31 runs; reconstructing the missing 12 moved the cycle from a
reported 3.76M to an actual **5.90M tokens**. Write the entry immediately after
each call — not at the end of the phase, not "later".

---

## Checkpointing (MANDATORY)

After EACH passed gate, write the workflow state to:

`${architecture.paths.docs_process_root}/checkpoints/{REQ-name}-state.json`

### Structure

```json
{
  "req_name": "REQ-YYYY-MM-DD-slug",
  "mode": "normal | reduced | lite | retroactive",
  "status": "in_progress | paused | completed | abandoned",
  "current_phase": "4a",
  "phases_completed": ["1", "2", "2.5", "3"],
  "phases_pending": ["4b", "5", "5.5", "6", "7"],
  "started_at": "ISO 8601",
  "last_updated": "ISO 8601",
  "artifacts": {
    "req_path": "docs/process/REQ-...",
    "story_paths": ["docs/process/stories/..."],
    "test_plan_path": "docs/process/test-plans/...",
    "frozen_schema_path": "docs/process/schemas/...",
    "review_reports": {
      "phase_3": null,
      "phase_5": null,
      "phase_5_5": null
    }
  },
  "phase_4a_progress": { "total_stories": 0, "stories_done": [], "current": null },
  "phase_4b_progress": { "total_stories": 0, "stories_done": [], "current": null },
  "telemetry_path": "docs/process/agent-telemetry/..."
}
```

### When to write

- After Phase 1 passes → create initial checkpoint.
- After EACH gate → update `phases_completed`, `current_phase`, `last_updated`.
- When the user pauses the session → `status: "paused"`.
- When Phase 7 completes → rename to `{REQ-name}-state.final.json`,
  `status: "completed"`.

### Resume protocol

If a session is resumed (new chat, crash recovery):

1. Read the most recent `{REQ-name}-state.json`.
2. If the user requested resumption or previously authorized continuous execution, announce the phase and continue without asking again. Otherwise obtain authorization to resume; never override an explicit pause.
3. Reload artifacts via paths in `artifacts.*`.
4. Continue from `phases_pending[0]`.

**Never skip phases when resuming** — if a phase says "completed" but
the artifact doesn't exist, treat the checkpoint as corrupt and ask the
user.

---

## Token Telemetry (MANDATORY)

Every `Agent` invocation returns a `<usage>` block with `total_tokens`,
`tool_uses`, and `duration_ms`. You MUST append it to a telemetry JSON
so the `final-auditor` (Phase 7) can analyze consumption by agent.

*(Claude Code: capture COMPLETENESS is enforced by harness — the
`telemetry_append` PostToolUse hook appends every subagent run to
`agent-telemetry/HOOK-LOG.jsonl` automatically. Your job is to ENRICH each
run into the REQ's telemetry JSON below — phase, `budget_ok`, `tool_uses_ok`,
`resumed`/`tokens_incremental` — and, at Phase 7, reconcile the curated JSON
against HOOK-LOG.jsonl: any run present in the log but missing from the JSON
is a debt to justify.)*
<!-- kuraka:discipline:telemetry -->

**File**:
`${architecture.paths.docs_process_root}/agent-telemetry/{REQ-name}-telemetry.json`

### Flow

1. After the **first** Agent call in the cycle, create the file:
   ```json
   {
     "req_name": "REQ-YYYY-MM-DD-slug",
     "mode": "normal | reduced | lite | retroactive",
     "runs": []
   }
   ```
2. After **each** Agent call, add an entry:
   ```json
   {
     "phase": "<int | string>",
     "agent": "<agent-name>",
     "mode": "<optional identifier>",
     "total_tokens": 0,
     "tool_uses": 0,
     "duration_ms": 0,
     "status": "ok | session_limit | interrupted | error",
     "produced": "<short description>",
     "size": "S | M | L",
     "variant": null,
     "tool_uses_cap": 0,
     "budget_ok": true,
     "tool_uses_ok": true,
     "resumed": false,
     "tokens_incremental": null
   }
   ```
3. If an agent is invoked multiple times in the same phase, each
   invocation is its own entry — use `mode` to disambiguate.
4. If you do **not** use `Agent` for a phase (direct orchestrator work),
   write a 0-token entry with `"agent": "orchestrator"` and the phase label, so
   the checkpoint ↔ telemetry reconciliation does not report a false debt.
   Combined runs use a `+`-joined label (`"1+2+2.5"`); the aggregator credits
   each phase in it.
5. Set `budget_ok` from **tokens vs the phase's "investigate if exceeds"
   threshold** — never from duration, and never default to `true` without
   actually comparing. A run cut short logs `status: "session_limit"` (so a
   0-token entry isn't read as "no work"); `budget_ok` then reflects only the
   tokens actually spent.
6. Set `tool_uses_ok` from **tool_uses vs the agent's cap** (table above) — same
   discipline: compare, never default to `true`.
7. **A RESUMED agent** (continued via `SendMessage` / resume rather than spawned
   fresh) reports the **cumulative** tokens of its whole transcript, not what the
   delta cost. For those entries set `"resumed": true` and record
   `"tokens_incremental"` — your best estimate of the delta's own spend. The
   `final-auditor` ranks by `tokens_incremental` when present, and
   `aggregate-telemetry.py` sums it instead of `total_tokens`.

   Two failures this prevents: (1) cycle totals inflate — REQ-20260804 reports
   2,729,123 tokens against a real ~1,985,000 (+37%) from 4 resumed runs of 15;
   (2) the T10 in-flight detector ("high tokens + low tool uses = re-pasted
   context") **false-positives on every resume** — that cycle's 2-line MEDIUM fix
   scored 53,641 tokens/use and was a flawless run. Without the flag, a
   pathological fresh agent and a healthy resume are indistinguishable.

**The numbers come ONLY from the harness.** `total_tokens`, `tool_uses` and
`duration_ms` are copied from the `<usage>` block the harness returns (or from
`HOOK-LOG.jsonl`), never from the agent's own report. Agents do **not**
self-report token or tool-use counts: self-reports ran below the harness in 3 of
10 and 6 of 7 runs (azure FD-3, possuite, petsuite, piscosdalston). If an agent's
report carries such a number anyway, it is ignored; if the harness value is
unavailable, write `null` + `"usage_source": "unavailable"` — or, when a figure is
genuinely needed, the estimate marked `[ESTIMACIÓN NO MEDIDA]` — never the
self-report as if measured.

The `final-auditor` reads this JSON in Phase 7 and produces the token
ranking in the retro. Missing telemetry degrades the retro but doesn't
block it.

---

## Model Routing

Model↔agent assignments are governed centrally in the vault's
`MODEL-ROUTING.yaml` (capability tiers: `frontier` / `heavy` / `balanced` /
`fast`, mapped per platform) and applied by `kuraka-apply-models.py`.

- **NEVER hand-edit a `model:` frontmatter line** — change the agent's tier in
  the map and re-run the apply script (`--check` flags drift).
- The authoritative current assignment is each agent's frontmatter *after*
  apply; the judgment GATES (po-analyst, architect-reviewer, code-reviewer,
  security-reviewer, final-auditor) ride the `frontier` tier.
- After a model change, restart Claude Code so the subagent re-registers.

---

## Kuraka system tooling

Scripts from the framework vault (`${KURAKA_VAULT}`) callable from any
branch / repo:

### `mount-kuraka.sh`

Mounts the Kuraka system into the current repo (rsync from vault,
updates `.gitignore`).

```bash
bash ${KURAKA_VAULT}/mount-kuraka.sh
# or with an alias in ~/.zshrc:
alias mount-kuraka='bash ${KURAKA_VAULT}/mount-kuraka.sh'
```

### `validate-kuraka.sh`

Validates frontmatter of agents / skills and detects orphan references.
Run before each new session to confirm everything is consistent.

```bash
bash ${KURAKA_VAULT}/validate-kuraka.sh
```

### `kuraka-inspect.py`

Stack detector for Brownfield onboarding. Scans a repo and produces a
JSON with backend / frontend / DB / testing / CI / containers detected.

```bash
python3 ${KURAKA_VAULT}/kuraka-inspect.py [dir]
# JSON to stdout, human summary to stderr
# Redirect to file to persist:
python3 ${KURAKA_VAULT}/kuraka-inspect.py > inspect-report.json
```

The `amauta` agent reads this JSON as its main input in Brownfield mode.

### `aggregate-telemetry.py`

Reads all JSONs from
`${architecture.paths.docs_process_root}/agent-telemetry/` and emits an
aggregated Markdown dashboard (per-cycle, per-agent, tokens / usage,
over-budget flags).

```bash
python3 ${KURAKA_VAULT}/aggregate-telemetry.py
# produces: ${architecture.paths.docs_process_root}/agent-telemetry/DASHBOARD.md
```

The `final-auditor` (Phase 7) MUST run it before writing the RETRO to
have aggregated data, not just from the current cycle.

### `tests/kuraka/`

Structural test suite for the system. Run after any change in
`.claude/agents/` or `.claude/skills/`:

```bash
python3 -m pytest tests/kuraka/ -v
```

Validates: frontmatter, model routing, kuraka split, output-schemas
coverage, no orphan references.

---

## Optimizations applicable in any mode

See `rules/17-kuraka-token-optimizations.md` for patterns T1–T5:

- **T1 Context digest** — the orchestrator reads reference files once
  and injects them as snippets in prompts.
- **T2 End-only verification** — for restyles / mechanical changes,
  typecheck / lint only at the end.
- **T3 Phase collapse** — combine Phase 1+2 into a single subagent for
  low-risk changes.
- **T4 Mapping-table stories** — compact AC as tables for substitution
  patterns.
- **T5 No auto-verify** — the orchestrator verifies, the agent doesn't.

Estimated impact: −35% on baseline for a UI-only cycle; up to −60% if
combined with infrastructure improvements (model routing, agent
registration).
