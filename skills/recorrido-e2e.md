---
name: recorrido-e2e
description: "Browser walk-through of every acceptance criterion: a deterministic Playwright spec acts in a real browser, asserts the visible result AND re-fetches the backend effect per step, against an isolated stack, and writes the RECORRIDO evidence doc. Satisfies Phase 6.8 for user-visible changes; its spec is promoted to the E2E regression suite in 6.5."
agent: "`e2e-tester`"
phase: "6.8 (and 6.5 promotion) — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Recorrido E2E — the browser walks every acceptance criterion

**Why:** the rework the RETROs keep measuring is "green tests + approved
reviews ≠ working feature" discovered late: a smoke run by hand, a fix, the
smoke repeated by hand, another fix (editorial F-15/F-31, petsuite: a PASS at
4/8 steps, guai-home: environment misdiagnosed 3×). A recorrido replaces the
manual loop with ONE reproducible artifact: a spec that performs the user's
actions in a real browser and checks, step by step, both what the user sees
and what the backend actually did. After a fix you re-run **the same spec** —
the verification costs a command, not a new session.

## Input

1. **The RECORRIDO table** from the test plan (Phase 2.5 / COMBINED —
   `test-plans/TEST-PLAN-{ticket}.md` §Recorrido). One row per step:

   | # | AC | User action | Expected UI | Expected backend effect (exact endpoint/query) | Evidence |
   |---|----|-------------|-------------|-----------------------------------------------|----------|
   | 1 | AC-1 | Opens `/agenda`, filters by technician X | list shows only X's slots | `GET /api/agenda?tecnico=X` → 200, every item `tecnicoId==X` | screenshot + response |
   | 2 | AC-2 | Books slot 10:00 | toast "Cita creada", slot disabled | row in `citas` with `estado='CONFIRMADA'` (`SELECT … WHERE id=:id`) | screenshot + row |

   The table is the contract: you EXECUTE it, you do not redesign it. If it is
   missing or a row has no backend effect, STOP and report
   `RECORRIDO SIN TABLA` — the orchestrator gets it from the planner. Never
   invent the expected effect from the code you are about to test.
2. The REQ **outcome sentence** (the one the solution outline declared). The
   last step of the table must prove it.
3. Stack: `kuraka.config.yaml` (`architecture.paths.frontend_root`, e2e root,
   base URL) + the stack profile's "E2E mechanics".

## Steps

1. **Pick the stack — isolated first.**
   - If the project adopted `validar-pr` and its `stack.sh` exists: bring up an
     isolated `vp*` stack with providers mocked (`stack.sh arriba vp<id>`), run
     against it, and bring it down at the end (`stack.sh abajo vp<id>`). It never
     touches the developer's stack.
   - Else: the dev stack the orchestrator booted and recorded in Phase 3.9
     (`baseline_*` in the checkpoint). Re-probe it before running (daemon up,
     port free) — `kuraka-policies` → "Definition of green".
   - Record which stack ran in the doc. Never against staging/prod.
2. **Discover selectors (optional, never the verdict).** Interactive browser
   tools (Playwright MCP, `.playwright-mcp/`, browser automation) may be used
   ONLY to find stable selectors (`getByRole`/`getByLabel`/`getByTestId`) and
   the live response shape. Nothing seen interactively counts as evidence.
3. **Write the spec** at `<e2e_root>/recorridos/<REQ>.spec.ts` (e2e root from
   config; default `<frontend_root>/tests/e2e`), starting from
   `.claude/templates/recorrido/recorrido.spec.template.ts`:
   - one `test.step()` per table row, named `#<n> <AC> — <action>`;
   - each step: perform the action → assert the UI → **re-fetch the backend
     effect** through `request` (API) or the project's read-only DB helper,
     asserting the exact fields of the table (rule 17 of `e2e-tester`);
   - log the URL actually hit per step and assert it equals the intended
     route (rule 10 — route provenance);
   - `trace: 'on'`, `screenshot: 'on'`, `video: 'retain-on-failure'`;
     outputs under `test-results/recorridos/<REQ>/`;
   - test data created by the recorrido is removed in teardown (or lives in a
     disposable tenant/stack).
4. **Run it once, in foreground, one runner per host**:
   `npx playwright test <e2e_root>/recorridos/<REQ>.spec.ts --reporter=line,json`
   (or the project's wrapper), redirecting output and exit code to files:
   `… > recorrido.log 2>&1; echo $? > recorrido.exit`. Never pipe the gate.
5. **Write the evidence doc** `${docs_process_root}/smoke-tests/RECORRIDO-<REQ>.md`
   from `.claude/templates/recorrido/RECORRIDO.template.md`: stack used, exact
   command, exit code, one row per step with PASS/FAIL, the UI assertion, the
   backend value observed (literal), and the artifact paths (screenshot,
   trace). Final line: verdict.

## Verdicts

- `PASS — n/n pasos` — every row executed and both assertions held.
- `PASS PARCIAL — n/m pasos` — any row skipped or unreachable; name each one
  and why. Never plain PASS (`e2e-tester` rule 16).
- `FAIL — paso #k` — first failing step, with its UI/backend observation and
  the trace path. A FAIL is a **finding, not something to fix inside the
  spec**: the orchestrator opens a bug-fix story in Phase 4, the implementer
  fixes the code, and **the same spec is re-run unchanged**.
- A step that fails only under load: re-run that spec isolated 3× before
  calling it flaky; record the three exits.

## Rules

- `e2e-tester` rules 15–19 apply verbatim: no green by weakening (diff the spec
  against its first version on every re-run and list any relaxed assertion),
  partial ≠ PASS, confirm at the source, environment causes need
  measurements, run hygiene.
- Backend assertions are mandatory per step. A step whose only check is the
  UI is reported `UI-ONLY` and counts as partial.
- The spec is a **regression asset**: it is committed with the cycle (subject
  to `workflow.commit_policy`) and Phase 6.5 promotes it instead of writing a
  second E2E for the same flow.
- Max 2 minutes per step-group test; split long walks into ordered files
  (`<REQ>.01.spec.ts`, …) only when a single run would exceed the harness turn
  ceiling.
