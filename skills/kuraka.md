---
name: kuraka
description: "Development orchestrator (kuraka, from Quechua *kuraq* — 'the elder'). Multi-agent workflow for end-to-end requirements: PO analysis → Story refinement → Test planning → Architect review → Implementation → Code review → Security → Tests → E2E → Deployment → Final audit. Scales the pipeline to the change's risk — see `kuraka-modes`."
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
| **Normal** (default) | 8 | Changes with logic, DB, API contracts, or integrations |
| **Reduced by risk** | 3–5 | UI-only, types-only, mechanical renames — see `kuraka-modes.md` and `rules/17-kuraka-token-optimizations.md` |
| **Lite** | 3 | Trivial changes meeting 9 strict criteria — see `kuraka-modes.md` |
| **Retroactive** | 4 | Code already implemented without workflow (anti-pattern, avoid it) |

**Default is Normal.** Justify and present the proposed pipeline to the
user **before** invoking any agent — they approve which phases to run. The
presentation is a markdown table (format mandated in §"Solution outline"
below), never a per-phase block list.

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

Only after the user validates (or corrects) the outline, propose the mode +
pipeline and request approval to launch. Phase 1's REQ must not contradict
the validated outline — if `po-analyst`'s analysis diverges, surface the
diff at the Phase 1 gate instead of absorbing it.

**Present the proposed pipeline as a MARKDOWN TABLE — never a per-phase
block list.** One row per phase (or per collapsed group), columns exactly:
`Fase | Agente | Skill | ¿Corre? | Justificación`. `¿Corre?` is one of
`Sí` / `Colapsada` / `Omitida`. Group every omitted phase into a SINGLE row
with its shared reason — do not spend one block per skipped phase. The table
is the readable, scannable form the user approves from; a flat list of
`Fase:` / `Agente:` / `Justificación:` lines separated by rules is a
presentation defect. Skeleton (fill from the actual decision):

| Fase | Agente | Skill | ¿Corre? | Justificación |
|------|--------|-------|:-------:|---------------|
| 1 PO Analysis | `po-analyst` | `analyze-requirement` | Sí | … |
| 2 Story Refinement | `story-refiner` | `refine-stories` | Sí | … |
| 3 Architect Review | `architect-reviewer` | `review-stories`+`schema-freeze` | Sí | Obligatoria: auth |
| 4a Backend | `backend-developer` | `implement-story` | Sí | El fix |
| 5 + 5.5 | `code-reviewer` + `security-reviewer` | `review-implementation` + `security-audit` | Sí | Obligatorias: auth |
| 6.8 Smoke | orquestador | (custom) | Sí | Gate que el REQ anterior dejó abierto |
| 7 Final Audit | `final-auditor` | `run-audit` | Sí | RETRO |
| 2.5, 6, 6.5, 6.7 | — | — | Omitida | Sin suite de tests / Playwright / Docker en el repo |

End with the launch question below the table (e.g. "¿Arranco con la
fase X?"). The mode line (Normal/Reduced/Lite + why) goes ABOVE the table,
one sentence — not folded into a phase row.

---

## Phase-Agent-Skill Map (Normal mode — 8 phases)

| Phase | Agent | Skill | Gate |
|-------|-------|-------|------|
| 1. PO Analysis | `po-analyst` | `requirement-consistency-check` → `analyze-requirement` | GATE0 no unresolved BLOCKER; user approves REQ |
| 2. Story Refinement | `story-refiner` | `refine-stories` | User approves stories |
| 2.5. Test Planning | `test-engineer` (mode: TEST_PLANNING) | `plan-tests` | User approves test plan |
| 3. Architect Review | `architect-reviewer` | `review-stories` + `schema-freeze` | No BLOCKERS; schema frozen |
| 3.9. Environment pre-flight | orchestrator (deterministic, ~0 tokens) | (see §Phase 3.9) | Stack boots; gate command runs; `baseline_red` recorded in checkpoint |
| 4a. Backend Impl | `backend-developer` | `implement-story` | `${stack.backend.lint_cmd}` + `${stack.backend.test_cmd}` OK |
| 4b. Frontend Impl | `frontend-developer` | `implement-story` | `${stack.frontend.lint_cmd}` + `${stack.frontend.typecheck_cmd}` + `${stack.frontend.test_cmd}` OK |
| 5. Code Review | `code-reviewer` | `review-implementation` | No BLOCKER or IMPORTANT |
| 5.5. Security Review | `security-reviewer` | `security-audit` | No CRITICAL |
| 6. Tests | `test-engineer` (mode: TEST_WRITING) | `analyze-testability` + `generate-unit-tests` + `generate-endpoint-tests` + `validate-coverage` | Tests pass |
| 6.5. E2E | `e2e-tester` | `generate-e2e-tests` | Playwright passes |
| 6.7. Deployment | `deployment-verifier` | `verify-deployment` | Docker / env / nginx / CI valid |
| 6.8. Smoke test runtime | orchestrator (with user approval) | (custom per cycle) | Smoke doc created or skip justified |
| 7. Final Audit | `final-auditor` | `run-audit` | Retro created **AND** vault backup done (exit 0) |

### Conditional agents

| Phase | Agent | Condition |
|-------|-------|-----------|
| 0 (pre-flow) | `jira-ticket-sync` | Only if the project tracks work in Jira (Jira MCP connected) and the user asks to sync/list pending tickets, or a cycle starts from a Jira ticket with no local file. Output feeds Phase 1 as REQ input. |
| 5 (sub) | `migration-reviewer` | Only if there are files in `${architecture.paths.migrations_root}` |

---

## Phases

### Phase 1 — PO Analysis
- Agent: `po-analyst` | Skill: `analyze-requirement`
- Output: `${architecture.paths.docs_process_root}/REQ-{YYYYMMDD}-{ticket}-{slug}.md`
- Content: scope IN/OUT, tables, endpoints, dependencies, risks, proposed stories.
- Gate: user approves REQ.
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
  not exist by Gate1, STOP and ask the user. Telemetry is not optional —
  RETRO-DD-1031 and RETRO-DD-1031-rerun were both blind audits because of
  this gap.

### Phase 2 — Story Refinement
- Agent: `story-refiner` | Skill: `refine-stories`
- Output: `${architecture.paths.docs_process_root}/stories/{ticket}-S{N}.md` (one per story).
- Content: description, verifiable AC, schema changes (if any), API contract, files.
- Rules: every identifier in `conventions.naming_language`; `conventions.null_syntax`; file paths from the stack profile; tenant scoping if `conventions.multi_tenant: true`.
- Gate: user approves stories.

### Phase 2.5 — Test Planning
- Agent: `test-engineer` (mode TEST_PLANNING) | Skill: `plan-tests`
- Output: `${architecture.paths.docs_process_root}/test-plans/TEST-PLAN-{ticket}.md`
- Content: testability constraints, test cases per story, fixtures, risks, estimated test count.
- Why: contract for the developer — the code must be testable per this plan.
- Gate: user approves test plan.

### Phase 3 — Architect Review + Schema Freeze
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

1. **Boot** the dev stack (or its health probe) once, if the project has a
   runtime component. A boot failure stops here.
2. **Run the exact gate command that will judge Phase 4** — the same
   `make check` / lint+typecheck+test string, unmodified — plus test
   collection, once.
3. **Record the baseline in the checkpoint** (`kuraka-policies.md` schema):
   - `baseline_red`: the list of ALREADY-failing tests/checks (empty when
     green). From here on, **"green" for every later gate means "no
     regression vs `baseline_red` + new tests green"** — this keeps the gate
     usable even on a repo with pre-existing red (sie DD1243: 8 pre-existing
     red suites made a raw full-suite gate meaningless).
   - `baseline_green`: one line describing the passing state (counts, date).
4. **Fix or waive**: a broken boot / dead gate command (can't fail, exit 127,
   doesn't propagate) is fixed BEFORE Phase 4, or explicitly waived by the
   user and recorded as an accepted risk. Pre-existing red tests are NOT
   fixed in this cycle's branch silently — they are either baseline-recorded
   or spun into their own story with the user's approval.

Gate: checkpoint contains `baseline_red` + `baseline_green`, and the gate
command is proven able to fail (rule 17 T7).

**Per-gate environment re-probe (not just once at 3.9).** Before EVERY later
gate that runs the test command (per-story 4a/4b, Phase 6, retro-gates), the
orchestrator re-runs a ~0-token probe: container daemon up (`docker info` or
equivalent) and the test-DB port free of foreign containers. On failure, print
the exact remediation command and **RE-POLL the probe until green** — never
advance on a verbal "it's running now" (sie-v2: a down daemon reported as up
cost lost turns in 3 cycles; a port-5434 collision was caught at zero cost by
exactly this probe).

### Phase 4 — Implementation

**PHASE 4 RULE:** a story is DONE only when its diff is committed on the
feature branch. The orchestrator commits after each story's `make test`
passes, before starting the next story. An uncommitted cycle is a lost
cycle (see RETRO-DD-1031 Incident A).

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

### Phase 6 — Tests
- Agent: `test-engineer` (mode TEST_WRITING) | Skills: `analyze-testability`,
  `generate-unit-tests`, `generate-endpoint-tests`, `validate-coverage`.
- Writes tests per the plan from Phase 2.5, following the stack profile's
  test idioms.
- Run: `${stack.backend.test_cmd}` + `${stack.backend.lint_cmd}`.
- Gate: all tests pass.

### Phase 6.5 — E2E
- Agent: `e2e-tester` | Skill: `generate-e2e-tests`
- Scope: only the golden path of changed flows.
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

**Skip request** (no automatic skip): the orchestrator may ASK the user
to skip 6.8 ONLY in these cases, and only with explicit approval:

- **Pure documentation**: the cycle doesn't modify executable code.
- **Refactor verifiable statically** with no behavioral change (rename,
  move files without touching logic, stricter typing without runtime
  change).
- **Documented technical impossibility** (e.g., requires infrastructure
  not available in dev). In this case, open a follow-up to add the
  smoke test when the infrastructure is available.

**"The agent cannot run it" ≠ "it cannot be run" (HARD).** If the smoke is
not automatable from the agent's host but the USER can run the app (their
IDE, a Windows box, a corp VPN), the smoke is NOT skipped — it becomes a
**user-executed smoke**: the orchestrator writes the full scenario FIRST
(preconditions, numbered steps, expected assertion per step) into
`SMOKE-{ticket}.md`, the user executes and reports, the agent records the
observed column + verdict. Handoffs quote the verdict **textually**
(`PASS PARCIAL` stays `PASS PARCIAL`, never a numeric paraphrase). For
cycles touching **auth / session / security-critical paths** this is a
BLOCKING gate with no deferral: without an executed smoke the cycle closes
**`PENDING-SMOKE`**, never DONE (facturacion-honorarios ENTRAID: conflating
the two let 5 stacked defects survive a "closed" cycle — the most expensive
defect in the vault's corpus, one full extra cycle + 5 user-in-the-loop
iterations).

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

### Phase 7 — Final Audit
- Agent: `final-auditor` | Skill: `run-audit`
- Output: `${architecture.paths.docs_process_root}/agent-retrospectives/RETRO-{REQ-name}.md`
  with:
  - Summary + timeline of rework.
  - Findings per agent + concrete prompt patches OR project-layer additions.
  - Systemic issues + improvements.
  - Token / latency telemetry.
- **MANDATORY last step — vault backup (never skip):** after the RETRO is
  written, snapshot the project's full Kuraka state into the central vault store:
  ```bash
  python3 "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/kuraka-backup.py" <project-root>
  ```
  This is a hard exit criterion: Phase 7 is NOT complete until this command
  exits 0. It (1) feeds `pattern-detector` across all projects and (2) preserves
  the cycle outside the solution's git so a branch switch can't lose it
  (`kuraka-restore.py` pastes it back on the next mount). If it is skipped for
  any reason, the cycle stays OPEN — do not report Phase 7 as done.

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

**Protocol if violated**:
1. Revert the change.
2. Announce the violation to the user.
3. Route through the correct agent.
4. Log the bypass in telemetry with `"agent": "orchestrator-direct"`.

This constraint was added after retros where the bypass produced type
errors and broken telemetry.

---

## General Kuraka rules

- **Never skip phases** when the pipeline includes them — every gate exists
  for a reason.
- **User approval between phases** — the orchestrator never auto-advances.
- **Schema freeze before Phase 4** — no DB changes during implementation.
- **Refresh stale stories** if the user makes corrections between phases.
- **One story at a time in Phase 4** — baby steps.
- **Token optimization**: apply `rules/17-kuraka-token-optimizations.md`
  (context digest, end-only typecheck, combined phases, mapping-table
  stories, no auto-verify, reviewer digests, delta-only re-runs).
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
  containing `--` broke an entire Web.config parse — 8 cascading errors with
  the user stuck in a live debug loop; 5 grep gates were wrong in one cycle).
- **Claims are reproduced, never quoted** (`rules/17` T9): before declaring
  any gate green, the orchestrator itself runs the cheap deterministic
  checks — `git diff` of every function a report claims "untouched",
  isolated run of each negative-assertion guard test, smoke-URL vs REQ-route
  match. A subagent's self-report — especially a negative claim ("I did NOT
  touch X") — is never evidence on its own (REQ-20260703: a false "untouched"
  claim survived the developer report and two reviews; two zero-token
  orchestrator gates caught it).
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
- [ ] Phase 1: PO Analysis
- [ ] Phase 2: Story Refinement
- [ ] Phase 2.5: Test Planning
- [ ] Phase 3: Architect Review + Schema Freeze
- [ ] Phase 3.9: Environment pre-flight (orchestrator — baseline_red recorded)
- [ ] Phase 4a: Backend Implementation
- [ ] Phase 4b: Frontend Implementation
- [ ] Phase 5: Code Review
- [ ] Phase 5.5: Security Review
- [ ] Phase 6: Tests
- [ ] Phase 6.5: E2E Tests
- [ ] Phase 6.7: Deployment Verification
- [ ] Phase 6.8: Smoke test runtime (MANDATORY — skip only with explicit justification)
- [ ] Phase 7: Final Audit (RETRO created)
- [ ] Phase 7: Vault backup — `kuraka-backup.py` exited 0 (MANDATORY — closes the cycle)
```

For Lite / Retroactive / Reduced-by-risk modes, see the templates in
`kuraka-modes.md`.
