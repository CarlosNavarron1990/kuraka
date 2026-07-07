---
name: kuraka-policies
description: "Cross-cutting Kuraka policies: retry, timeout, token budget, failure fallback, checkpointing, and telemetry. Applies in any mode."
---

# Kuraka — Policies

Cross-cutting policies that apply in any Kuraka mode (Normal,
Reduced-by-risk, Lite, Retroactive).

---

## Agent Invocation Policy

Every `Agent` call has retry and timeout policies to prevent silent
failures from propagating through the workflow.

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

### Timeout policy

- **Max 10 minutes per invocation** (`duration_ms > 600_000`).
- **Timeout escalates to the user**: "Agent {agent} has been running 10+
  min. Continue, abort, or change strategy?"
- **Legitimate long tasks**: rare. If you expect to exceed 10 min, split
  the task into smaller units.

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

When a test / typecheck result is the gate for advancing a story or phase,
run the gate command WITHOUT a pipe and assert on **its own** exit code
(e.g. `make test-run`, then check `$?`). NEVER pipe the gate command
(`make ... | tail`, `... | head`, `... | grep`) — the shell reports the
LAST command's exit code (the pipe's), so a failing suite can read as
green. If output must be trimmed, redirect to a file and read the file;
the gate still reads the test command's own exit code.

Reference: REQ-20260611 S3 advanced on a FALSE GREEN (`make ... | tail`)
while the suite was failing at collection (Sentry/jinja2 infra bug). See
`rules/17-kuraka-token-optimizations.md` Rule T7.

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
probe, a frozen-schema cross-check — run the command through `rtk proxy <cmd>`
(raw, unfiltered) instead of the rewritten form. Never run a contract cross-check
on truncated output.

---

## Token Budget (recommended)

Nominal budget per phase to detect deviations:

| Phase | Target | Investigate if exceeds |
|---|---:|---|
| 1 PO Analysis | 80–120K | 200K |
| 2 Story Refinement | 60–100K | 180K |
| 2.5 Test Planning | 60–100K | 150K |
| 3 Architect Review | 80–120K | 180K |
| 4a Backend Impl (per story M) | 100–200K | 400K |
| 4b Frontend Impl (per story M) | 100–200K | 400K |
| 5 Code Review | 70–120K | 200K |
| 5.5 Security Review | 60–100K | 180K |
| 6 Tests (per story M) | 80–150K | 300K |
| 6.5 E2E | 50–100K | 200K |
| 6.7 Deployment | 30–60K | 120K |
| 7 Final Audit | 60–100K | 150K |

These thresholds are **tokens (model compute)** — the only real spend signal.
**Wall-clock `duration_ms` is NOT a budget gate**: it includes tool/DB/container
wait, so analysis phases and DB-bearing test-writing are legitimately slow without
overspending. A run that is slow but in-band on tokens is a latency artifact —
investigate it separately, never mark it over budget (guai: 7 cycles ran 31–86 min
yet reported `budget_ok: true`; the metric conflated wait with compute).

**Action if a phase exceeds "investigate if exceeds" (tokens)**:
1. Abort the phase if still running.
2. Analyze telemetry (which files were read? how many tool_uses?).
3. Apply patterns T1–T10 from `rules/17-kuraka-token-optimizations.md`.
4. Re-launch with an optimized prompt.

**Mid-cycle consequence (not just retro material)**: a completed run that
exceeded its threshold MUST be logged `budget_ok: false` immediately, and the
NEXT run of the same agent type in this cycle MUST carry a pre-extracted
digest (T1/T8/T9) — over-budget without corrective action on the next
invocation is an orchestrator failure, not a telemetry footnote.
(REQ-20260703: every agent ran 2–3× its target, one over its hard cap, and
all 19 entries were recorded `budget_ok: true` — the check never fired.
`aggregate-telemetry.py` now recomputes `budget_ok` and flags contradictions
in the dashboard.)

---

## Checkpointing (MANDATORY)

After EACH gate approved by the user, write the workflow state to:

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

- After approval of Phase 1 → create initial checkpoint.
- After EACH gate → update `phases_completed`, `current_phase`, `last_updated`.
- When the user pauses the session → `status: "paused"`.
- When Phase 7 completes → rename to `{REQ-name}-state.final.json`,
  `status: "completed"`.

### Resume protocol

If a session is resumed (new chat, crash recovery):

1. Read the most recent `{REQ-name}-state.json`.
2. Confirm with user: "Resuming {REQ-name} from phase {current_phase}. Continue?"
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
     "budget_ok": true
   }
   ```
3. If an agent is invoked multiple times in the same phase, each
   invocation is its own entry — use `mode` to disambiguate.
4. If you do **not** use `Agent` for a phase (direct orchestrator work),
   omit the entry — only track real invocations.
5. Set `budget_ok` from **tokens vs the phase's "investigate if exceeds"
   threshold** — never from duration, and never default to `true` without
   actually comparing. A run cut short logs `status: "session_limit"` (so a
   0-token entry isn't read as "no work"); `budget_ok` then reflects only the
   tokens actually spent.

The `final-auditor` reads this JSON in Phase 7 and produces the token
ranking in the retro. Missing telemetry degrades the retro but doesn't
block it.

---

## Model Routing

Each agent has a model assigned in its frontmatter according to cost / judgment:

| Model | Agents | Why |
|---|---|---|
| **opus** | `po-analyst`, `architect-reviewer`, `security-reviewer`, `final-auditor` | Complex reasoning, multiple sources, strategic judgment |
| **sonnet** | `story-refiner`, `backend-developer`, `frontend-developer`, `code-reviewer`, `test-engineer` | Balanced implementation and review |
| **haiku** | `deployment-verifier`, `pattern-detector`, `migration-reviewer`, `e2e-tester` | Mechanical checks, pattern matching, smoke tests — much cheaper than sonnet |

Changing a model: edit `model:` in the corresponding agent's frontmatter
and restart Claude Code so it re-registers the subagent.

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
