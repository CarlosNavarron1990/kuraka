---
name: kuraka
description: "Development orchestrator (kuraka, from Quechua *kuraq* — 'the elder'). Multi-agent workflow for end-to-end requirements: PO analysis → Story refinement → Test planning → Architect review → Implementation → Code review → Security → Tests → E2E → Deployment → Final audit. Scales the pipeline to the change's risk — see `kuraka-modes`."
disable-model-invocation: true
user-invocable: false
---

# Kuraka — Development Orchestrator

> *Kuraka* (also "curaca") — from Quechua `kuraq` = "the elder". The
> local leader who coordinated the *ayllus* (specialist groups) under a
> larger plan. In this system, the Kuraka is the orchestrator that
> drives specialist agents through the phases of the development cycle.

This skill defines the **main flow**. Two companion files complement it:

- `kuraka-modes.md` — flow variants (Discovery, Bootstrap, Brownfield,
  Standard, Compliance, Reduced-by-risk, Lite, Retroactive) and when to
  use each.
- `kuraka-policies.md` — cross-cutting policies (retry, timeout,
  telemetry, checkpoints).

---

## Prerequisites

Before starting you need:

1. A requirement document (REQ) or ticket reference.
2. A description of the requirement (from the ticket, markdown, or user
   input).

Also required: `kuraka.config.yaml` at the project root. If missing, ask
the user to run `kuraka init` (or copy the template from the framework's
`kuraka-artifacts/config-schema.yaml`).

**Preflight — run BEFORE Phase 1** (once per cycle; ~2 s, no model cost):

```bash
python3 "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/kuraka-doctor.py" <project-root>
```

It verifies the RESULT, not exit codes: config present and its `project.name`
agreeing with the slug the central store already uses, specialization layer,
mount manifest stamped with the current suite, local agent tuning in sync with
the store, every RETRO archived, telemetry attached, `docs/process` mirrored.
Exit 0 = green, start the cycle. Non-zero: run it with `--fix` (it repairs the
safe ones and re-checks) and act on what it still reports — a missing manifest
needs `kuraka-mount.py <project> --update`, a slug mismatch is a naming decision.
**Do not start a cycle on a project whose config is missing**: without
`docs_process_root` the agents scatter REQs, retros and telemetry, and the cycle
becomes unauditable (guai-home-marketplace ended with its retros split across two
directories, 36 of them duplicated).

If the user hasn't provided a requirement, ask before proceeding. If the
user has only an **idea, not a requirement** (and wants to explore the
bases of the system), do not start Phase 1 — run the Discovery mode first:
the `facilitate-discovery` skill (Tinkuy council) produces a design brief
that then feeds `po-analyst`. See `kuraka-modes.md` → Discovery.

---

## Initial decision: mode and pipeline

**BEFORE invoking any agent**, evaluate the surface of the change and
decide:

1. **Which layers does it touch?** UI-only / types-only / service /
   repository / schema / integration / auth.
2. **How many files and estimated LOC?**
3. **Is there new logic? Contract change? PII / security? Migration?**

With that, pick a mode:

| Mode | Phases | When |
|------|:------:|------|
| **Lite** | 3 | No new schema, API contract, auth or integration surface — see `kuraka-modes.md` |
| **Reduced by risk** | 3–5 | UI-only, types-only, mechanical renames — see `kuraka-modes.md` and `rules/17-kuraka-token-optimizations.md` |
| **Normal** | 8 | Schema, API contracts, auth, integrations, or logic spanning layers |
| **Retroactive** | 4 | Code already implemented without workflow (anti-pattern, avoid it) |

### The pipeline is built UP, never pruned down

**Start at Lite and escalate**, naming the trigger that forces each extra
phase. Do NOT start from the 8 phases and prune: measured over 100 archived
cycles, that default produced a median Normal cycle of **1.81M tokens against
601K for a Reduced one**, and Lite went **unused in 100 of 100 cycles** —
nothing was ever demoted into it.

Every subagent invocation costs **120–180K tokens regardless of its phase**
(measured median over 1197 runs; the floor is the agent's startup, not its
work). The cost of a cycle is therefore `~150K × number of invocations`, and
the only lever that moves it is **invoking fewer agents**. Count the planned
invocations before launching and present that number with the pipeline — it
is the cycle's budget, and `rules/17` T0 makes the cap an action, not advice.

| Extra phase | Median cost | Trigger that justifies it |
|---|---:|---|
| 2 + 2.5 split out of Phase 1 | +350K | ≥4 stories, or stories the user must approve separately from the REQ |
| 3 architect + schema freeze | +151K | Schema change, new endpoint, or API contract change |
| 5.5 security | +112K | Auth, PII, tokens, crypto, or an external provider |
| 6.5 E2E | +147K | A user-visible flow spanning ≥2 screens |
| 6.7 deployment | +94K | Config, env vars, migrations, or infra |

**3.95 acceptance tests RED is a MOVE, not an extra.** The `test-engineer`
invocation that used to write tests after the code (Phase 6) now runs BEFORE
it and writes the acceptance tests from the plan; Phase 6 only runs when
`validate-coverage` shows gaps or the plan has INTERNAL cases. Count 3.95 as
one invocation whenever Phase 4 runs on a change with an API/contract/AC-testable
surface; do not count a separate Phase 6 unless a gap is expected.

**Never cut** (they are cheap or free, and they are what catches the rework
that costs a whole cycle): Phase 3.9 pre-flight (deterministic, ~0 tokens),
Phase 6.8 smoke, Phase 6.9 user validation (~0 tokens — a script records it),
and Phase 7 final audit — median 47K, the cheapest phase in the suite.
Phase 3.95 (acceptance tests RED) is not cut either whenever Phase 4 touches an
API / contract / AC-testable surface — it is the tester invocation moved before
the code, not an extra one.

### The mode gate — offer the viable modes, recommend one, let the user choose

Do NOT present a single take-it-or-leave-it pipeline. **Offer the modes that
are viable for this change, say which one you recommend and why, and let the
user pick.** The user decides how much process this change deserves; your job
is to make that decision informed and cheap.

**Step 1 — surface analysis (orchestrator, deterministic, ~0 tokens).** Before
any subagent, establish from the requirement and the code: files likely
touched, rough LOC, and which of the five triggers are PRESENT — schema /
migration, new endpoint or contract change, auth-PII-security surface,
integration or provider, multi-screen flow. This costs nothing and it is what
makes the menu honest.

**Step 2 — build the menu.** Offer 2–3 modes via `AskUserQuestion`, each with
its invocation count, its budget, and what it gives up:

```
Superficie: 3 archivos, ~120 LOC · disparadores presentes: ninguno

  ▸ LITE — 3 invocaciones ≈ 450K            [RECOMENDADO]
    Omite architect, security, E2E, deployment. Ningún disparador los pide.
  ▸ REDUCIDO — 6 invocaciones ≈ 900K
    Suma architect. Elígelo si el módulo es frágil o quieres el schema freeze.
  ▸ NORMAL — 13 invocaciones ≈ 1.9M
    Las 8 fases. Elígelo si esto entra en una release auditada.
```

**Step 3 — state the recommendation and its reason in ONE line**, never a
paragraph of hedging. Recommend by trigger count, not by intuition: 0
triggers → Lite; 1 → Reduced; ≥2, or ≥4 stories, or ≥10 files → Normal.

**When the change is big, say so plainly and still show the cheap option.**
"Se sugiere Normal: hay migración y cambio de contrato" — and Reduced stays on
the menu with what it gives up, because the user may know the migration is
trivial. What does NOT go on the menu is a mode that breaks Lite's safety
criteria: list it as considered-and-discarded with the failing criterion on
one line (`LITE — no aplica: hay migración`), so the user sees it was weighed.
If they ask for it anyway, §The user can FIX the mode governs.

**Skip the menu when the user already chose.** If `$ARGUMENTS` names a mode,
or the user stated one in the pre-flow conversation, run it and announce the
invocation count. Asking again what has been answered wastes their turn and
reads as second-guessing.

Whatever is chosen, record it (`mode`, `mode_selected_by`) and present the
resulting pipeline with its per-phase justification **before** invoking the
first agent.

### The user can FIX the mode — and that choice is not re-litigated

The escalation ladder is the orchestrator's *default reasoning*, never a
constraint on the user. The user fixes the mode either in the command
arguments (`/kuraka <requerimiento> — modo normal`) or by answering the
pipeline gate ("no, corre Normal completo"). Both are equally binding.

**Escalating is always obeyed, immediately and silently.** If the user asks
for Normal — or for one specific extra phase — run it. Do not re-propose a
cheaper mode, do not restate the token cost you already showed, do not ask
"¿seguro?". They saw the budget line; asking for more phases anyway IS the
decision. Announce the new invocation count and start. The user knows things
about the change that the surface analysis cannot see (a fragile module, an
incident last month, an auditor reading the diff) and those reasons are not
owed to you.

**De-escalating below the safety criteria is the one thing that is refused.**
Lite's 7 criteria (`kuraka-modes.md`) are not preference, they are what makes
the omitted phases safe to omit: if the change carries a migration, a contract
change, an auth surface or an integration, Lite does not apply no matter who
asks. Say ONCE, in one sentence, which criterion fails and what the minimum
safe pipeline is — then run that. If the user reaffirms after being told, that
is their call: run what they asked, and record the override in the Workflow
Status (`mode forced by user, criterion X waived`) so the RETRO can see it.

**Record who chose the mode.** Write `mode_selected_by: user | orchestrator`
into the cycle's telemetry JSON alongside `mode`. Without it the store cannot
tell a mode the analysis *chose* from a mode the user *imposed*, and the
cross-project measurements that produced this ladder (`rules/17` T13) would
drift on their own recommendations.

### Solution outline — mandatory CONCLUSION of the pre-flow conversation

The pre-flow conversation never ends with a bare "shall I start the flow?".
It ends with a **solution outline** the user can validate for completeness —
this is what reveals, before any agent token is spent, whether the intended
functionality is whole or a piece is missing. Present, in this order:

1. **Outcome sentence** — one sentence: "when this cycle closes, the system
   can X when Y." This is the SAME sentence Phase 6.8 will verify at close —
   declared up front, verified at the end. If the cycle drifts from it, the
   drift must be user-approved, never absorbed silently.
2. **Implementation steps** — the concrete surfaces the solution is expected
   to touch, in execution order: endpoints/routes (REAL paths, verified in the
   code, not guessed), services, tables/migrations, UI screens, integrations,
   config vars. Mark each NEW or MODIFY. This set seeds the scope-fidelity
   check (`rules/17` T9): anything an implementer later changes outside it is
   a flag, not a silent addition.
3. **Explicitly OUT** — what this cycle will NOT do, so the user confirms the
   missing pieces are intentional, not forgotten.
4. **Open questions** — anything the outline could not resolve. These feed
   Phase 1's GATE0 as questions; they are never silently assumed.

Present the outline and viable mode + pipeline together, and obtain one authorization to launch. Respect any mode the user already selected. Phase 1's REQ must not contradict
the validated outline — if `po-analyst`'s analysis diverges, surface the
diff at the Phase 1 gate instead of absorbing it.

**When the outline can't be validated in prose, show it**: run the
`prototype-data-preview` skill. It builds ONE interactive HTML artifact whose
left half is the real screen (real markup, real brand tokens) and whose right
half is every table that intervenes, with the real value each column would
receive as the user operates the mock. Reach for it when the user answers a
question with "show me", when two options differ only in invisible state
(what persists, what is skipped, what is silently discarded), or when the
Phase 3 schema freeze has to decide whether a datum is stored at all. It is
the orchestrator's own tool — a subagent cannot publish artifacts — and its
output is a decision artifact in `docs/process/`, never shipped code.

Its payoff is not the picture: it is that the table/column inventory the user
just validated **is** the inventory Phase 3 will freeze. In the cycle that
produced this skill (REQ-20260908) the write-preview surfaced, in one glance,
a map pin the UI had been promising and the database had never received.

---

## Phase-Agent-Skill Map (Normal mode — 8 phases)

| Phase | Agent | Skill | Gate |
|-------|-------|-------|------|
| 1. PO Analysis | `po-analyst` | `requirement-consistency-check` → `analyze-requirement` | GATE0 no unresolved BLOCKER; REQ matches authorized scope |
| 2. Story Refinement | `story-refiner` | `refine-stories` | Stories match authorized scope; no unresolved blockers |
| 2.5. Test Planning | `test-engineer` (mode: TEST_PLANNING) | `plan-tests` | Test plan covers authorized scope; no unresolved blockers |
| 3. Architect Review | `architect-reviewer` | `review-stories` + `schema-freeze` | No BLOCKERS; schema frozen |
| 3.9. Environment pre-flight | orchestrator (deterministic, ~0 tokens) | (see §Phase 3.9) | Stack boots; gate command runs; `baseline_red` recorded in checkpoint |
| 3.95. Acceptance tests RED | `test-engineer` (mode: TEST_FIRST) | `generate-endpoint-tests` / `generate-unit-tests` from the plan's oracles | Every ACCEPTANCE case has a test, RED for the right reason; `kuraka-testlock.py lock` recorded |
| 4a. Backend Impl | `backend-developer` | `implement-story` | `${stack.backend.lint_cmd}` + `${stack.backend.test_cmd}` OK; locked acceptance tests green; `kuraka-testlock.py verify` exit 0 |
| 4b. Frontend Impl | `frontend-developer` | `implement-story` | `${stack.frontend.lint_cmd}` + `${stack.frontend.typecheck_cmd}` + `${stack.frontend.test_cmd}` OK |
| 5. Code Review | `code-reviewer` | `review-implementation` | No BLOCKER or IMPORTANT |
| 5.5. Security Review | `security-reviewer` | `security-audit` | No CRITICAL |
| 6. Coverage gaps (CONDITIONAL) | `test-engineer` (mode: TEST_WRITING) | `validate-coverage` → `analyze-testability` + `generate-unit-tests` / `generate-endpoint-tests` | Gaps + INTERNAL cases covered with sourced expectations; tests pass; testlock verify exit 0 |
| 6.5. E2E | `e2e-tester` | `generate-e2e-tests` (promotes the recorrido spec) | Playwright passes |
| 6.7. Deployment | `deployment-verifier` | `verify-deployment` | Docker / env / nginx / CI valid |
| 6.8. Smoke test runtime | `e2e-tester` (recorrido, user-visible change) or orchestrator | `recorrido-e2e` / (custom per cycle) | RECORRIDO or SMOKE doc green, or skip justified |
| 6.9. User validation + adjustments | orchestrator + user (`kuraka-ajuste.py`, ~0 tokens) | — | User acceptance recorded (`aceptar`) or explicit `cerrar` with reason; every adjustment logged verbatim |
| 7. Final Audit | `final-auditor` | `run-audit` | Retro created (with `## Efectividad`) **AND** vault backup done (exit 0) **AND** `kuraka-doctor` verde |

### Agent binding (HARD) — always the configured specialist, never a generic agent

Every `Agent` invocation in a Kuraka cycle MUST set `subagent_type` to the
**exact agent named in the map above** (or in §Conditional / §On-demand), so
the project's mounted definition (`.claude/agents/<name>.md` — its prompt,
tools, preloaded skills and `model:` tier) is what actually runs.

- **FORBIDDEN as a phase agent:** `general-purpose`, `Explore`, `Plan`,
  `claude`, `fork`, or omitting `subagent_type` (which defaults to a generic
  agent). Never "emulate" a specialist by pasting its role into a generic
  agent's prompt — the role then exists only in the orchestrator's context,
  without the specialist's tools, skills, hooks or digest protocol.
- **Do not pass `model:`** on a phase invocation — the tier comes from the
  agent's own frontmatter, which follows the vault's `MODEL-ROUTING.yaml`.
  **Never downgrade a tier to save tokens**: budget is cut by invoking fewer
  agents (`rules/17` T13), never by weaker models. Override only when the user
  explicitly asks.
- **If the named agent is not available** (missing from the session's agent
  list, or the call errors with an unknown type): STOP, report which agent is
  missing, and point to `python3 kuraka-doctor.py --fix` / `kuraka-mount.py
  --update` + restarting the session (agents register at session start).
  Never fall back to a generic agent.
- The telemetry `agent` field records the real `subagent_type`; a cycle whose
  telemetry shows a generic agent (or a fused `a+b+c` slot) in a phase slot
  **fails Phase 7**.
- Orchestrator-run steps (3.9, 6.8, deterministic checks) and Ultra Ahorro
  (zero subagents by design) are unaffected.

(Sources: sie-v2 DD-1530 — every phase from 3 on ran as `general-purpose` with
an inline role prompt; possuite P0/P1 — fused agent slots made telemetry
unusable.)

### Conditional agents

| Phase | Agent | Condition |
|-------|-------|-----------|
| 5 (sub) | `migration-reviewer` | Only if there are files in `${architecture.paths.migrations_root}` |

### On-demand agents (outside the phase map)

These agents are NOT part of any cycle phase. Invoke them only on their
trigger; never substitute them for a phase agent.

| Agent | Invoke when | Never as a substitute for |
|-------|-------------|---------------------------|
| `pentest-auditor` | The user asks for a whole-app security audit / pentest | Phase 5.5 (`security-reviewer` owns the cycle diff) |
| `sentry-resolver` | The user asks to triage / review Sentry issues | — |
| `deploy-diagnostician` | Deploy runbook work, or a deploy/runtime failure to diagnose | Phase 6.7 (`deployment-verifier` owns pre-release config checks) |
| `provider-contract-validator` | Validating/migrating a provider API contract (Postman ↔ spec ↔ code) | — |
| `migration-deployability` | Before merging a branch with migrations into a deployment branch | Phase 5 sub (`migration-reviewer` owns DDL quality) |
| `checkmarx-remediation` | A Checkmarx One scan needs analysis / a remediation plan | — |
| `jira-ticket-sync` | The project tracks work in Jira and the user asks to sync/see pending tickets | Phase 1 (it feeds `po-analyst`, doesn't replace it) |
| `pr-writer` | The user asks for the PR text/description after the cycle (or after `validar-pr`) | Phase 7 (`final-auditor` owns the RETRO; `pr-writer` only drafts the PR body) |

**Pre-PR gate (skill, not agent):** when the project adopted `validar-pr`
(`.claude/project/validar-pr/config.sh` exists), the cycle's branch reaches a
PR only through `validar-pr.sh` — the `pr_gate` hook blocks `gh pr create|ready`
without an APROBABLE report for HEAD. With `workflow.commit_policy: user` the
orchestrator runs it without `--crear-pr` and hands the report to the user.

Entry agents (`inti` → `arki` → `llimpi` for greenfield, `amauta` for
brownfield) run once per project — see `kuraka-modes.md` (Bootstrap /
Brownfield). `llimpi` is an orchestrator-run skill (`/llimpi`), not a
subagent: it produces the prototype and the `docs/plan/vN/` cycle plan; a
greenfield project with a plan starts each cycle from the prompt of its next
`docs/plan/vN/Cnn-*.md`.

---

## Phases

> **Phases 1, 2 and 2.5 run COMBINED in a single `po-analyst` invocation by
> default** (mode `COMBINED`, `rules/17` T3). Split them into three agents only
> when a trigger from §Initial decision applies. Measured over 197 archived
> runs, the three separately cost a median 473K (123K + 171K + 179K) against
> 123K combined — the split is the single most expensive default in the suite.
> Combined, one output carries the REQ, the stories and the test plan, and the
> the orchestrator validates all three against the authorized scope at one gate. Every hard precondition below (GATE0,
> GATE1) still applies to the combined run.

### Phase 1 — PO Analysis
- Agent: `po-analyst` | Skill: `analyze-requirement`
- Output: `${architecture.paths.docs_process_root}/REQ-{YYYYMMDD}-{ticket}-{slug}.md`
- Content: scope IN/OUT, tables, endpoints, dependencies, risks, proposed stories.
- Gate: REQ matches the authorized scope and has no unresolved blockers.
- **GATE0 PRECONDITION (HARD — runs before analyze-requirement):**
  `po-analyst` MUST run the `requirement-consistency-check` skill first.
  If it returns `BLOCKED`, STOP: turn each Blocker into an
  `AskUserQuestion`, record answers verbatim in the REQ
  ("Resolved clarifications"), and only then proceed. Do NOT dispatch to
  Phase 2/4 while any BLOCKER is unresolved. Re-run the skill on the
  delta whenever the user expands scope mid-cycle ("ahora también…",
  "te faltó…"); a new BLOCKER re-opens GATE0. Rationale: DD-1031 rework
  (≈13 runtime iterations, one near-revert, duplicate migration work)
  was caused by fragmented scope + reversible decisions without a
  recorded value test. See `docs/process/IMPROVEMENTS-DD-1031.md`.
- **GATE1 PRECONDITION (HARD):** the per-Agent telemetry JSON file for this
  REQ must exist and be appended after every Agent invocation. If it does
  not exist by Gate1, create or repair it from available evidence, recording unknown values as null. If that cannot be done, stop and explain the blocker. Telemetry is not optional —
  RETRO-DD-1031 and RETRO-DD-1031-rerun were both blind audits because of
  this gap.

### Phase 2 — Story Refinement
- Agent: `story-refiner` | Skill: `refine-stories`
- Output: `${architecture.paths.docs_process_root}/stories/{ticket}-S{N}.md` (one per story).
- Content: description, verifiable AC, schema changes (if any), API contract, files.
- Rules: every identifier in `conventions.naming_language`; `conventions.null_syntax`; file paths from the stack profile; tenant scoping if `conventions.multi_tenant: true`.
- Gate: stories match the authorized scope and have no unresolved blockers.

### Phase 2.5 — Test Planning
- Agent: `test-engineer` (mode TEST_PLANNING) | Skill: `plan-tests`
- Output: `${architecture.paths.docs_process_root}/test-plans/TEST-PLAN-{ticket}.md`
- Content: testability constraints, test cases per story **each with its
  oracle** (input → expected result + the source that fixes it: AC / REQ §
  / frozen contract / rule) and its kind (`ACCEPTANCE` | `INTERNAL`),
  fixtures, risks, estimated test count.
- Why: contract for the developer — and the ONLY place a test's expected value
  may come from. A value the spec does not determine is a GATE0 question.
- Gate: test plan covers the authorized scope and has no unresolved blockers.

### Phase 3 — Architect Review + Schema Freeze

**CONDITIONAL** (median 151K): runs when the change touches a DB schema, adds
an endpoint, or alters an API contract — i.e. whenever there is something to
freeze. Otherwise Phase 5's review covers the structural check; record the
omission and its trigger-absence in the Workflow Status, never silently.

- Agent: `architect-reviewer` | Skills: `review-stories` + `schema-freeze`
- Validates stories and test plan; freezes schema before implementation.
- Output: report with verdict + `${architecture.paths.docs_process_root}/schemas/SCHEMA-FROZEN-{ticket}.md`
- Gate: all BLOCKERs resolved + schema frozen.

### Phase 3.9 — Environment pre-flight (orchestrator, deterministic, ~0 tokens)

**Runs in EVERY cycle that reaches Phase 4, in every mode.** The first time
the real stack is exercised must NOT be during implementation — pre-existing
breakage otherwise bills itself to the cycle, confounds gates, and gets fixed
opportunistically in-branch (the pattern recurred in 5/5 vault projects,
11+ cycles: missing deps, diverged test-DBs, dead lint configs, suites that
never typechecked, pre-existing red tests making `exit 0` undefined).

The ORCHESTRATOR runs these directly (no subagent, `rules/17` T9 style):

0. **Read the project's orchestrator conventions first.** Every
   orchestrator-run step (3.9, the per-story gates, 6.8) is bound by the
   project layer just like an agent is: read the layer files whose
   frontmatter `applies_to` includes `orchestrator`, and any
   `conventions/environment-traps.md` / `conventions/gate-commands.md` in the
   project layer (`.claude/project/` — or the platform's equivalent), before
   running a command.
   They record the traps this host already hit (wrong runner, stale volume,
   CRLF, `._*` files, a gate that needs a flag). (guai-agents-platform-azure
   FD-20, 4 retros: the orchestrator re-hit documented traps because only
   agents read the layer.)
1. **Boot** the dev stack (or its health probe) once, if the project has a
   runtime component. A boot failure stops here. The environment must be
   **current** before any gate is trusted — recreate containers after a
   dependency/lockfile/migration/Dockerfile change, bind every green to
   `gates_measured_at` (HEAD), one test runner per host: see
   `kuraka-policies.md` → "Definition of green" (not repeated here).
2. **Run EVERY gate command any later phase will be judged by — one per
   workspace**, unmodified, plus test collection, once. Not just the primary
   test suite. For a backend+frontend repo that means, at minimum:
   ```
   backend:   ${stack.backend.test_cmd}      (e.g. make test-run)
   frontend:  ${stack.frontend.typecheck_cmd}  AND  ${stack.frontend.lint_cmd}
              AND  ${stack.frontend.test_cmd}
   ```
   Record exit code, counts and a `baseline_red` list **for each one
   separately**. A gate with no recorded baseline cannot distinguish
   *pre-existing* from *regression* — REQ-20260801 baselined only the backend
   suite, and when `npm run lint` returned 1 mid-cycle the baseline had to be
   reconstructed after the fact to find out whose fault it was.
3. **Record the baseline in the checkpoint** (`kuraka-policies.md` schema):
   - `baseline_red`: the list of ALREADY-failing tests/checks (empty when
     green). From here on, **"green" for every later gate means "no
     regression vs `baseline_red` + new tests green"** — this keeps the gate
     usable even on a repo with pre-existing red (sie DD1243: 8 pre-existing
     red suites made a raw full-suite gate meaningless).
   - `baseline_green`: one line describing the passing state (counts, date).
   - The baseline is measured **in this cycle, on this branch's HEAD**. Never
     copy `baseline_red`/`baseline_green` from another cycle's checkpoint or
     RETRO, even a recent one on the same branch — a reused baseline hides
     whatever changed in between (editorialcesarvallejo F-31).
   - `baseline_migration_head`: the DB migration head at cycle start (e.g.
     `alembic heads`, `prisma migrate status`), plus `baseline_git_head`.
     **Re-run the head command (deterministic, ~0 tokens) before INTERPRETING
     any per-story gate result.** If it moved, write that into the checkpoint
     *before* judging the gate: a red gate with a moved head is suspected
     collision with parallel work, not your own regression.

     REQ-20260804: migration `000020` from a parallel branch (DD-1067) landed in
     the same working tree mid-cycle at 13:11 and produced 3 chain failures that
     had to be diagnosed by hand. Related convention (`rules/13`): chain
     assertions are **membership** (`"000019" in chain`), never equality with
     `head` — an equality assertion turns any foreign merge into a false red.
4. **Fix or waive**: a broken boot / dead gate command (can't fail, exit 127,
   doesn't propagate) is fixed BEFORE Phase 4, or explicitly waived by the
   user and recorded as an accepted risk. Pre-existing red tests are NOT
   fixed in this cycle's branch silently — they are either baseline-recorded
   or spun into their own story with the user's approval.

**Per-gate environment re-probe (not just once at 3.9).** Before EVERY later
gate that runs the test command (per-story 4a/4b, Phase 6, retro-gates), the
orchestrator re-runs a ~0-token probe: container daemon up (`docker info` or
equivalent) and the test-DB port free of foreign containers. On failure, print
the exact remediation command and **RE-POLL the probe until green** — never
advance on a verbal "it's running now" (sie-v2: a down daemon reported as up
cost lost turns in 3 cycles; a port collision was caught at zero cost by
exactly this probe). *(Restored 2026-11 harvest — 1.1.0 item P7, lost
2026-08-12.)*

Gate: checkpoint contains `baseline_red` + `baseline_green`, and the gate
command is proven able to fail (rule 17 T7).

### Phase 3.95 — Acceptance tests RED (spec first)

**Runs whenever Phase 4 runs on a change with an API / contract / AC-testable
surface, in every mode with a separate tester** (Lite does it inside L2, see
`kuraka-modes.md`). The expected value of a test comes from the SPEC, never
from the code: tests written after the implementation, by reading it, assert
whatever the code does — bugs included — and the mutation proof cannot catch
that (it proves the test is sensitive, not that its expectation is right).

- Agent: `test-engineer` (mode TEST_FIRST).
- Input: the plan's `ACCEPTANCE` rows (with oracles), the frozen
  schema/contract, the 3.9 baseline, existing test infra and the interfaces the
  stories DECLARE. Not the implementation under change.
- Output: one test per ACCEPTANCE row, asserting the plan's oracle verbatim
  and citing its source; each RED for the right reason (assertion failure or a
  not-yet-existing endpoint/attribute — never an import/collection/fixture
  error); then `python3 "${KURAKA_VAULT}/kuraka-testlock.py" lock <root> --req
  <REQ> <files…>` and the files + red evidence in the checkpoint.
- A row without a sourced expectation → open question to the user, not a test.
- Gate: every ACCEPTANCE row has a locked RED test with pasted evidence.

**Locked means locked.** In Phase 4 and later no agent edits a locked test.
A developer who believes one is wrong stops and reports `conflicto de
especificación` with the plan line; the orchestrator asks the user; if the
user agrees the test (and the plan row) change, record it with
`kuraka-testlock.py unlock --file F --motivo "..." --aprobado-por user` and
re-lock after the fix. Never relax a test to match the code silently.

### Phase 4 — Implementation

**PHASE 4 RULE:** a story is DONE only when its diff is secured. What
"secured" means depends on `workflow.commit_policy` (kuraka.config.yaml):

- `orchestrator` (default): the story's diff is committed on the feature
  branch. The orchestrator commits after each story's gate passes, before
  starting the next story. An uncommitted cycle is a lost cycle (see
  RETRO-DD-1031 Incident A).
- `user`: the team owns every git mutation. The orchestrator **never** runs
  `git add/commit/merge/rebase/push/stash/checkout` — a story is DONE when its
  gate passed, a ready-to-paste commit message (conventional, listing the
  story's files) is written into the checkpoint/story file and shown to the
  user, and `kuraka-backup.py` has run so the cycle state survives outside
  git. Remind the user to commit before the next story if stories share files.
  (guai-agents-platform-azure FD-18 / -aws: the per-story commit contradicted
  teams that forbid agent commits.)

Two sub-phases that can run in parallel if stories are independent (when
`workflow.parallel_implementation: true`):

- **4a Backend** — Agent: `backend-developer` | Skill: `implement-story`
  - Order: defined by the stack profile for `${stack.backend.framework}`.
  - Check after each file: `${stack.backend.lint_cmd}`
  - Check after each story: `${stack.backend.typecheck_cmd}` (when the stack
    defines one — e.g. `tsc --noEmit`, `mypy`) **then** `${stack.backend.test_cmd}`

- **4b Frontend** — Agent: `frontend-developer` | Skill: `implement-story`
  - Order: defined by the stack profile for `${stack.frontend.framework}`.
  - Check after each file: `${stack.frontend.lint_cmd}` + `${stack.frontend.typecheck_cmd}`
  - Check after each story: `${stack.frontend.test_cmd}`

Shared rules: `conventions.max_file_loc` and `conventions.max_function_loc`
respected; no hardcoded values; no magic strings (per
`conventions.enums_for_states`); all imports at file top; no commented-out code.

Gate 4: all stories implemented + checks green. **"Green" = lint +
typecheck + test all pass.** A test runner that transpiles per-file (vitest,
jest) does NOT typecheck the graph — never accept "tests green" as proof of a
clean build. If the stack defines `typecheck_cmd` for a workspace, a story is
not done until that command exits 0. (Source: kuraka-control LL-014 — an
invalid cast rode green ~3 cycles because the gate ran the test runner only.)
Gate 4 also requires: the locked acceptance tests of every implemented story
GREEN, and `python3 "${KURAKA_VAULT}/kuraka-testlock.py" verify <root> --req
<REQ>` exit 0 (a locked test modified or deleted without an `unlock` record
fails the gate).

### Phase 5 — Code Review
- Agent: `code-reviewer` | Skill: `review-implementation`
- Input: the orchestrator passes the reviewer digest (`rules/17` T8 + T9):
  frozen schema + invariants + the per-function `git diff` hunks, so the
  scope-fidelity check is a table comparison, not a surface re-read.
- 6D framework: correctness, security, performance, maintainability,
  readability, tests.
- Output: report with findings table by severity (BLOCKER / IMPORTANT /
  MINOR / SUGGESTION / PRAISE).
- Gate: BLOCKER and IMPORTANT resolved, AND scope fidelity confirmed — the
  set of changed functions equals the set the stories authorize as MODIFY,
  cited from a diff the reviewer ran (never from the developer's self-report).
  The orchestrator additionally re-runs the diff itself for every function a
  report claims "untouched" (zero-token deterministic check, `rules/17` T9).

### Phase 5.5 — Security Review
- Agent: `security-reviewer` | Skill: `security-audit`
- Scope: OWASP Top 10, secret scan, tenant isolation (if multi-tenant),
  auth per endpoint, GDPR (if applicable).
- Vocabulary: CRITICAL / HIGH / MEDIUM / LOW / INFO.
- Gate: no CRITICAL; HIGH explicitly accepted by the user.

### Phase 6 — Coverage gaps (CONDITIONAL)
- Runs only when `validate-coverage` reports gaps against the plan or the plan
  has `INTERNAL` cases (helpers whose interface did not exist before Phase 4).
  The acceptance tests already exist (3.95) — Phase 6 never rewrites them.
- Agent: `test-engineer` (mode TEST_WRITING) | Skills: `validate-coverage`,
  `analyze-testability`, `generate-unit-tests`, `generate-endpoint-tests`.
- The code is read to find WHAT is untested, never WHAT to expect: every
  expected value cites its plan case / AC / rule; a behavior that contradicts
  the plan is a finding (bug or spec gap), never an adjusted expectation.
- Run: `${stack.backend.test_cmd}` + `${stack.backend.lint_cmd}` + testlock verify.
- Gate: all tests pass; testlock verify exit 0.

### Phase 6.5 — E2E
- Agent: `e2e-tester` | Skill: `generate-e2e-tests`
- Scope: only the golden path of changed flows.
- **When a recorrido ran (6.8)**, 6.5 is its PROMOTION into the regression
  suite — no second spec for the same flow. Order in Normal mode: the
  recorrido runs right after Phase 6 (it is cheaper to find the broken step
  before 6.5/6.7), and 6.5 promotes it.
- Legitimate skip: pure-backend cycle with no user-facing changes.
- Gate: Playwright green.

### Phase 6.7 — Deployment Verification
- Agent: `deployment-verifier` | Skill: `verify-deployment`
- Validates: `docker-compose config`, env vars documented in
  `.env.example`, nginx (if applicable), CI runs lint+test, migrations
  apply, build smoke test.
- Gate: no BLOCKER.

### Phase 6.8 — Smoke test runtime (MANDATORY in EVERY cycle)

**Applies ALWAYS.** This phase is not optional or conditional on the
type of change. Every Kuraka cycle — regardless of integration, scope,
or mode (Normal / Lite / Retroactive) — must exercise the end-to-end
flow before declaring the cycle closed. The guiding principle is
**"green tests + approved reviews ≠ working feature"**.

**The orchestrator CANNOT invoke Phase 7 (Final Audit / RETRO)** without
having completed or explicitly justified this phase. If it tries, it
must revert and complete 6.8 first.

**User-visible change → the smoke IS a browser recorrido** (`recorrido-e2e`,
run by `e2e-tester`, every mode including Lite — budget it as one more
invocation). A real browser walks the RECORRIDO table of the test plan
(one row per acceptance criterion: action → expected UI → expected backend
effect with its exact endpoint/query) through a deterministic Playwright spec
that asserts the screen AND re-fetches the backend effect per step, against
the isolated `validar-pr` stack when the project has one (providers mocked),
else the stack recorded in 3.9. Its doc
`smoke-tests/RECORRIDO-{REQ}.md` satisfies step 4 below. Interactive browser
tools only discover selectors; the verdict is the spec's exit code. A
`FAIL — paso #k` opens the bug-fix story (step 5) and, after the fix, **the
same spec is re-run unchanged** — that is what removes the manual
smoke→fix→smoke loop the RETROs keep billing. The planner (Phase 2.5 /
COMBINED) owns the table; if it is missing, ask `po-analyst` for the delta
rather than letting the tester design steps from the code it is testing.
Backend-only / non-visual cycles keep the scenario below.

**Mandatory steps:**

1. **Identify the principal end-to-end flow** of the change. For ANY
   change, articulate in one sentence: "the result of this cycle is
   that the system can now X when Y." If you can't articulate it, the
   scope of the cycle is poorly defined and you have to go back to
   Phase 1.
   This must be the SAME outcome sentence declared in the pre-flow
   **solution outline** (see "Initial decision") — verify THAT sentence,
   not a freshly invented one. If the cycle legitimately drifted (user-
   approved deltas), verify the updated sentence and note the drift in
   the smoke doc.
   - Examples per change type:
     - **Integration**: "incoming event → entity persisted in DB → sync
       to external service".
     - **New endpoint**: "authenticated HTTP request → validation →
       service → repository → verified response".
     - **Refactor**: "the observable behavior before and after the
       refactor is identical for the 2-3 critical flows it touches".
     - **UI / Frontend**: "the user navigates to the page, executes the
       main action, sees the expected result". Dev server + browser, not
       just a build.
     - **Schema / migration**: "the migration applies on a real (or
       snapshot) dump, the affected queries still work, the rollback is
       safe".
     - **Bug fix**: "the scenario that reproduced the bug now produces
       the correct behavior".
2. **Design ONE smoke test runtime scenario** that exercises that flow
   with:
   - **The exact production route/entry-point the REQ names** — pinned from
     the REQ text, never from whichever matching handler the code resolves
     first. Log the actual URL/route hit and assert it equals the intended
     one; a green smoke against another route is a FAIL (REQ-20260703: smoke
     "passed" against a legacy register endpoint and masked a scope drift).
   - Realistic input (real anonymized data or fixtures as close to
     production as possible). NOT trivial synthetic mocks generated by
     the agent.
   - Real dependencies or high-fidelity mocks (HTTP mock with verified
     responses, real DB with seeds applied, not generic `MagicMock()`).
   - Verification that ALL components fit together: data contracts,
     expected shapes, side effects, persistence, external calls, error
     handling where applicable.
3. **Execute the scenario** end-to-end, not the pieces separately.
4. **Document the result** in
   `${architecture.paths.docs_process_root}/smoke-tests/SMOKE-{ticket}.md`:
   - Exact command executed.
   - Verified output (with literal quote or screenshot if UI).
   - Components exercised (closed list).
   - Components NOT exercised and why — every component of the flow not
     exercised needs explicit justification ("stub accepted by scope of
     ticket", "requires prod credentials not available in dev", etc.).
5. **If the smoke test fails**, open a bug-fix story in Phase 4 before
   advancing to Phase 7. **Do not close the cycle with a broken
   end-to-end flow.**

**"The agent cannot run it" ≠ "it cannot be run" (HARD).** If the smoke is
not automatable from the agent's host but the USER can run the app (their
IDE, another OS, a corporate VPN), the smoke is NOT skipped — it becomes a
**user-executed smoke**: the orchestrator writes the full scenario FIRST
(preconditions, numbered steps, expected assertion per step) into
`SMOKE-{ticket}.md`, the user executes and reports, the orchestrator records
the observed column + verdict. Handoffs quote the verdict **textually**
(`PASS PARCIAL` stays `PASS PARCIAL`, never a numeric paraphrase). For
cycles touching **auth / session / security-critical paths** this is a
BLOCKING gate with no deferral: without an executed smoke the cycle closes
**`PENDING-SMOKE`**, never DONE (facturacion-honorarios ENTRAID: conflating
the two let 5 stacked defects survive a "closed" cycle — one full extra
cycle + 5 user-in-the-loop iterations). *(Restored 2026-11 harvest — 1.1.0
item P12, lost 2026-08-12.)*

**Skip request** (no automatic skip): the orchestrator may ASK the user
to skip 6.8 ONLY in these cases, and only with explicit approval:

- **Pure documentation**: the cycle doesn't modify executable code.
- **Refactor verifiable statically** with no behavioral change (rename,
  move files without touching logic, stricter typing without runtime
  change).
- **Documented technical impossibility** (e.g., requires infrastructure
  not available in dev). In this case, open a follow-up to add the
  smoke test when the infrastructure is available.

If the user approves the skip, **document it in the Phase 7 RETRO** as
an accepted risk with the textual justification.

**Gate**:
`${architecture.paths.docs_process_root}/smoke-tests/SMOKE-{ticket}.md`
exists and green (agent-run or user-executed), OR skip justification
approved by the user and documented in the RETRO. Auth/session/security
cycles: no skip — executed smoke or `PENDING-SMOKE`.

**Why**: lessons such as the smoke-test invariant generalize a common
failure mode — `${stack.backend.test_cmd}` green + reviews approved +
RETRO closed does NOT guarantee the pieces work together. Without this
phase, any cycle can close with green tests and a broken feature —
the hidden cost is shifted to post-close and doesn't appear in formal
metrics.

### Phase 6.9 — User validation and adjustments (effectiveness) — MANDATORY

**Applies in EVERY mode** (Normal, Reduced, Lite, Retroactive; Ultra Ahorro
records a one-line acceptance with the same script). Green gates and a green
smoke prove the cycle did what Kuraka understood; only the user can say it is
what they wanted. This phase measures that gap, and turns it into framework
learning instead of silent rework.

The ledger is written by a **script, never by hand** (zero tokens):
`python3 "${KURAKA_VAULT}/kuraka-ajuste.py" <cmd> <project-root> --req <REQ> …`
→ `${architecture.paths.docs_process_root}/ajustes/AJUSTES-<REQ>.{jsonl,md}`.

1. **Present** the outcome sentence (the one declared in the solution outline)
   and the 6.8 evidence (RECORRIDO / SMOKE verdict, quoted textually). Ask the
   user to try it and answer: *acepto* / *hay que ajustar*.
2. **Every adjustment the user asks for is recorded VERBATIM against the
   RUNNING cycle** before any code moves — never folded silently into a fix:
   `kuraka-ajuste.py add … --tipo <bug|ux|cambio-alcance|falto-preguntar|falto-hacer|entorno> --debio "<phase agent>" --texto "<user's words>"`.
   Classify honestly — `--debio` names the phase/agent that should have caught
   it (e.g. `1 po-analyst` for a question never asked, `6.8 recorrido` for a
   flow the smoke did not walk). `falto-preguntar` / `falto-hacer` are the
   signal that improves Kuraka; `cambio-alcance` is a real new decision (record
   it, and get the delta approved like any scope change).
3. **Resolve** through the normal machinery: a Phase 4 delta by the developer
   agent (gates, review on the delta), then re-run **the same** recorrido /
   smoke spec, `kuraka-ajuste.py resolver --id N --resolucion "…"`, and open
   the next round with `kuraka-ajuste.py ronda`. Back to step 1.
4. **Close** only with the user's explicit acceptance:
   `kuraka-ajuste.py aceptar --req <REQ> [--nota "…"]`. If the user stops
   without accepting, record why: `kuraka-ajuste.py cerrar --motivo "…"`.
5. **On acceptance, run Phase 7 IMMEDIATELY, in the same session.** Do not end
   the turn on "¡listo!": the 2026-11 store audit found ~100 cycles across
   projects left open without a RETRO because the session ended right after the
   user validated — their lessons never reached the layer or the vault.

Gate: `kuraka-ajuste.py estado --req <REQ>` shows `aceptacion` ≠
`sin-aceptacion` (or a recorded `cerrar` reason) and 0 unresolved adjustments
(or each pending one carried as an explicit follow-up). The Phase 7 RETRO's
`## Efectividad` section is built from `estado --json`.

### Phase 7 — Final Audit
- Agent: `final-auditor` | Skill: `run-audit`
- Output: `${architecture.paths.docs_process_root}/agent-retrospectives/RETRO-{REQ-name}.md`
  with:
  - Summary + timeline of rework.
  - Findings per agent + concrete prompt patches OR project-layer additions.
  - Systemic issues + improvements.
  - Token / latency telemetry.
  - `## Efectividad (validación del usuario)` from `kuraka-ajuste.py estado
    --json`: every `falto-preguntar` / `falto-hacer` becomes a project-layer
    patch applied here and tagged `harvest-candidate`.
- **Agent Tuning & Patch Application:** Apply approved project-layer or agent prompt patches directly to the project's mounted agent files (`.agents/agents/`, `.agents/skills/`, `.agents/project/` for Antigravity; `.claude/` for Claude Code; `.cursor/` for Cursor; `.codex/` for Codex). This closes the retro-apply loop so future cycles benefit from tuned agent behavior.
- **MANDATORY last step — vault backup (never skip):** after the RETRO is
  written and patches applied, snapshot the project's full Kuraka state into the central vault store:
  ```bash
  python3 "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/kuraka-backup.py" <project-root> [--target <antigravity|claude|cursor|codex>]
  ```
  This is a hard exit criterion: Phase 7 is NOT complete until this command
  exits 0 — and since 2026-09 it **refuses to close a cycle whose RETRO has no
  `## Confidence:` line** (exit 1; the state is still snapshotted, it is the
  CYCLE that stays open). That check lives in the script, not in a hook, because
  the script is the only gate every platform runs: Antigravity / Cursor / Codex
  have no hook API, and relying on prose there produced entire projects of
  verdict-less cycles. A cycle archived with no telemetry is warned about, not
  blocked. Deliberate exception: `--allow-incomplete-retro`. It (1) feeds `pattern-detector` across all projects and (2) preserves
  the cycle outside the solution's git so a branch switch can't lose it
  (`kuraka-restore.py` pastes it back on the next mount). If it is skipped for
  any reason, the cycle stays OPEN — do not report Phase 7 as done.
- **Then verify the backup actually landed** (exit 0 is not evidence):
  ```bash
  python3 "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/kuraka-doctor.py" <project-root>
  ```
  It re-reads the store and confirms this cycle's RETRO is archived, its
  telemetry attached, the agent tuning applied above is snapshotted, and
  `docs/process` mirrored. Report its verdict in the RETRO. Non-zero closes
  nothing: run `--fix` and re-check. Every silent breakage found in the
  2026-08 store audit (a whole agent suite mis-snapshotted as "overrides",
  telemetry never attached, a rename splitting a project's history) passed a
  green `kuraka-backup` first.

---

## Project guidelines win — Kuraka absorbs, never overwrites

Many projects arrive with their own conventions: `.claude/rules/`,
`CLAUDE.md`, skills and hooks tracked in the project's git (azure:
`validar-pr`, `security-audit`, `code-review-equipo`, `rules/01–13`), plus the
specialization layer. Order of precedence on conflict, highest first:

1. The user's instruction in this session.
2. The project's own tracked guidelines (`CLAUDE.md`, `.claude/rules/*` not
   shipped by Kuraka, tracked project skills/hooks) and the layer
   (`.claude/project/`).
3. Kuraka defaults (agents, skills, rules 16–23, policies).

- **Never edit a project-tracked file** to make Kuraka fit — not during mount,
  backup or a cycle (the mount skips them and reports them as project-owned).
  If a Kuraka rule contradicts a project rule, follow the project's and note
  the conflict in the RETRO as a candidate for the layer or for the harvest.
- **Same-name skill (project vs Kuraka):** the project's copy is the one on
  disk and the one that runs. Agents that preload a Kuraka skill by that name
  (AGENT-HARNESS `skills:`) then receive the project's text — today
  `security-reviewer` → `security-audit`; `validar-pr` is not preloaded. When
  the project's skill is a different process (azure `security-audit` = the
  team's OWASP/RGPD checklist), tell the agent in its prompt: "the preloaded
  `security-audit` is the project's checklist — apply it AND the Phase 5.5
  contract in your definition (`security-reviewer.md`)". The Kuraka contract
  is the floor, the project's checklist adds to it.
- **Same-purpose tools:** prefer the project's (its `validar-pr`, its gate
  commands from `conventions/gate-commands.md`, its e2e harness) and feed
  their output into the phase gates instead of running a Kuraka duplicate.

---

## Orchestrator constraint (do NOT touch code directly)

The orchestrator (the Claude running Kuraka) **NEVER** creates or modifies
source files (`${architecture.paths.backend_root}`,
`${architecture.paths.frontend_root}`,
`${architecture.paths.tests_root}`,
`${architecture.paths.migrations_root}`) before Phase 4. All
implementation goes through `backend-developer` or `frontend-developer`,
with no exceptions for "the change is trivial".

**Legitimate exception**: the orchestrator may edit `docs/` (REQ,
stories, test plans, retros) and Kuraka system files (`.claude/skills/`,
`.claude/agents/`, `.claude/rules/`).

**Mode exception**: in **Ultra Ahorro** (`kuraka-ahorro.md`, selected by the
user) the main session IS the implementer, for the files it declared in advance
and nothing else. That mode runs no phases and no gates, so this constraint
does not apply to it — and it is never a way to bypass this constraint from
inside a delegated cycle: switching modes mid-cycle is the user's call.

*(Claude Code: enforced by harness — the `orchestrator_guard` PreToolUse hook
blocks main-session writes under the configured code roots; the documented
user-approved exception is a one-shot `touch .claude/hooks/ALLOW-ORCH-WRITE`.
Do not spend turns policing this yourself.)*
<!-- kuraka:discipline:orchestrator-writes -->

This constraint was added after retros where the bypass produced type
errors and broken telemetry.

---

## General Kuraka rules

- **Never skip phases** when the pipeline includes them — every gate exists
  for a reason.
- **Continuous execution:** Once the user has authorized the scope and mode, advance through passing gates without requesting further approval. Record each gate, checkpoint, and evidence; report progress without ending the turn. Pause only for unresolved material decisions, failed gates that cannot be remedied, explicit user pauses, or actions requiring separate authorization. Never waive a failed gate silently.
- **Schema freeze before Phase 4** — no DB changes during implementation.
- **Refresh stale stories** if the user makes corrections between phases.
- **One story at a time in Phase 4** — baby steps.
- **Token optimization**: apply `rules/17-kuraka-token-optimizations.md`
  (context digest, end-only typecheck, combined phases, mapping-table
  stories, no auto-verify, reviewer digests, delta-only re-runs).
- **Claims are reproduced, never quoted** (`rules/17` T9): before declaring
  any gate green, the orchestrator itself runs the cheap deterministic
  checks — `git diff` of every function a report claims "untouched",
  isolated run of each negative-assertion guard test, smoke-URL vs REQ-route
  match. A subagent's self-report — especially a negative claim ("I did NOT
  touch X") — is never evidence on its own (REQ-20260703: a false "untouched"
  claim survived the developer report and two reviews; two zero-token
  orchestrator gates caught it).
- **Frozen contracts are never paraphrased** (HARD): an implementation/fix
  prompt references SCHEMA-FROZEN by anchor and pastes the **literal contract
  block + the delta** — never rewritten signatures or re-described wiring
  locations (two prompt-divergence defects came from paraphrase). Any text a
  parser will read (XML/JSON/YAML/SQL/config) is pasted in final syntax or
  delegated to an implementer; after ANY config-file edit the orchestrator
  validates it with the real parser at ~0 tokens (e.g.
  `python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1])" f`)
  — never by "reading it". Presence/absence claims about config entries use a
  parser, not grep: comments defeat grep in both directions (an XML comment
  containing `--` broke a whole config parse — 8 cascading errors; 5 grep
  gates were wrong in one cycle). *(Restored 2026-11 harvest — 1.1.0 item P15,
  lost 2026-08-12.)*
- **Green tests ≠ working feature** (universal guiding principle): EVERY
  Kuraka cycle, regardless of change type or integration, must exercise
  the end-to-end flow before closing (see Phase 6.8).
  `${stack.backend.test_cmd}` green + approved reviews are NECESSARY but
  NEVER SUFFICIENT to declare a cycle done. If the smoke test runtime
  isn't viable, justify explicitly and record as accepted risk in the
  RETRO. **This rule applies to ANY change**: backend, frontend,
  refactor, bug fix, migration, integration, or cosmetic.

---

## Workflow Status Templates

For Normal mode, add at the start of the REQ:

```markdown
## Workflow Status
<!-- GENERATED from the checkpoint's `phases_completed` — never hand-ticked.
     Regenerate this block from the checkpoint at every phase transition; a
     box is [x] only if its phase id is in phases_completed. The rows for
     3.9, 6.8, 6.9 and 7 are NEVER deleted from the block: if the mode skips one,
     the row stays with "SKIPPED — <reason>". -->
- [ ] Phase 1+2+2.5: PO Analysis + Stories + Test Plan (`po-analyst` COMBINED — default)
      <!-- split into three lines ONLY when a trigger forced separate agents; name the trigger -->
- [ ] Phase 3: Architect Review + Schema Freeze (CONDITIONAL — schema / new endpoint / contract; if omitted, state the absent trigger)
- [ ] Phase 3.9: Environment pre-flight (orchestrator — baseline_red recorded)
- [ ] Phase 3.95: Acceptance tests RED + locked (`test-engineer` TEST_FIRST — N tests, red evidence)
- [ ] Phase 4a: Backend Implementation
- [ ] Phase 4b: Frontend Implementation
- [ ] Phase 5: Code Review
- [ ] Phase 5.5: Security Review
- [ ] Phase 6: Coverage gaps (CONDITIONAL — only if validate-coverage shows gaps / INTERNAL cases)
- [ ] Phase 6.5: E2E Tests
- [ ] Phase 6.7: Deployment Verification
- [ ] Phase 6.8: Smoke test runtime (MANDATORY — skip only with explicit justification)
- [ ] Phase 6.9: User validation — `kuraka-ajuste.py aceptar` (rounds: N · adjustments: N · faltó: N)
- [ ] Phase 7: Final Audit (RETRO created, with `## Efectividad`)
- [ ] Phase 7: Vault backup — `kuraka-backup.py` exited 0 (MANDATORY — closes the cycle)
- [ ] Phase 7: State verified — `kuraka-doctor.py` sin hallazgos (el backup dejó lo que decía dejar)

Planned invocations: N  (budget ≈ N × 150K — see §Initial decision)
```

**The status is a VIEW of the checkpoint, not a second source of truth.**
At each phase transition the orchestrator rewrites the block from
`phases_completed` (plus `skipped_phases` with their reasons) — it does not
tick boxes by memory. A status that disagrees with the checkpoint is a Phase 7
finding. (guai-agents-platform-azure FD-7/FD-26, 7 retros: hand-maintained
status went stale or silently dropped 3.9/6.8.)

For Lite / Retroactive / Reduced-by-risk modes, see the templates in
`kuraka-modes.md` — the same generation rule applies.
