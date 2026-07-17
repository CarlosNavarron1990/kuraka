---
name: generate-e2e-tests
description: "Generate Playwright E2E tests for critical user flows. Focus on golden path, not exhaustive coverage. Used in Phase 6.5."
agent: "`e2e-tester`"
phase: "6.5 — see `kuraka`"
---

# Generate E2E Tests

Write Playwright tests for the user flows affected by this cycle, for
the project described in `kuraka.config.yaml`.

## Input

- REQ document (to identify user-facing flows).
- Frontend changes (to know what UI to test).
- Existing E2E tests (to reuse patterns).
- `.claude/project/glossary.md` if present (to use the project's domain
  vocabulary in test names).

## Steps

1. **Identify critical flows** from the REQ:
   - Did auth change? → test auth flow.
   - Did a feature change? → test its happy path.
   - Did an integration change? → test end-to-end through the
     project's entry point (consult
     `.claude/project/conventions/cross-provider-conventions.md` or
     equivalent if present for the project's integration patterns).

2. **Check existing tests** — don't duplicate, update instead.

3. **Write Page Objects** for any new pages / components.

4. **Write test specs** — one file per flow.

5. **Run in headless mode** — `npx playwright test` (or the project's
   `${stack.frontend.test_cmd}` if it wraps Playwright).

6. **Verify they pass in CI** — not just locally.

## CRUD recipe per operation (one spec each)

Framework-general; adapt the mutation-endpoint / success-signal / soft-delete / identity tokens to
the project (`.claude/project/conventions/*.md` + stack profile). See the e2e-tester agent's "CRUD
test playbook" for the full form. All inherit: fresh per-test auth, golden-path STRICT + labeled
expected-reds, gating short-circuit, locale-aware dates.

- **CREATE (insert):** fill only REQUIRED fields (probe 422 for the set) with unique values → submit
  → assert success → read the new hash from the (minimal, no-envelope) create response, decode
  tenant from `X-User` → **TEARDOWN** (delete what you created; real `add-*` pollute).
- **UPDATE / EDIT:** per-field round-trip — pick target on page 1 (paginator, not gated search);
  assert EVERY editable field pre-loads; change each; save; re-fetch; assert each persisted; REVERT.
  Selects + readonly datepickers = observe-only; decimals via `Number()`.
- **DELETE (soft-delete):** create a throwaway or pick expendable; delete; assert it LEAVES the
  active list (or badge flips), not physical removal; restore if supported; never hard-delete a real
  record.
- **READ / LIST:** assert `Array.isArray(data)` (list-success ≠ mutation-success); assert the
  denormalized fields the UI renders; capture + freeze the live response shape before asserting.

## Rules

1. **Max 2 minutes per test**.
2. **No hardcoded waits** — always `waitFor*`.
3. **Robust selectors** — `getByRole`, `getByLabel`, `getByTestId`.
4. **Golden path only** — unit tests handle edge cases.
5. **Use fixtures for repeated setup** (auth, seed data).
6. **Clean up test data** in `afterEach`.
7. **Full-page snapshot for overlay/modal state** — a subtree snapshot can hide a
   sibling dialog and fabricate an anomaly.
8. **Disambiguate empty-state from broken-state** — when asserting an absence
   (empty list, hidden controls), inspect the underlying data/headers to tell
   "legitimately empty" from "silently broken"; never close on that ambiguity.
9. **Live-backend auth** — if the backend rotates single-use refresh tokens, log
   in FRESH per test via the real UI (`{auto:true}` fixture); never a shared
   `storageState` across files. Validate the harness on ≥2 spec files, and confirm
   any config flag exists in the installed Playwright version (LL-016).
10. **Diagnostic suite (golden-path STRICT)** — when the goal is to MAP backend
    bugs on a real tenant: any 4xx/5xx is a FAIL that names route+endpoint+status
    +message into a matrix via `testInfo.annotations` (reporter ≠ worker process);
    a known-broken endpoint is still CALLED + THROWS, F-task-labeled, never
    skipped; distinguish list-success (`Array.isArray`) from mutation-success
    (`error:"0"`) (LL-017).
11. **Edit = per-field round-trip** — pre-load + assert every editable field,
    edit each, save, RE-FETCH, assert persisted, then REVERT. Decimals are strings
    → `Number()` compare / `Number(x)+1` bump. Reach off-page rows via the
    paginator (not gated search); guard disabled boundary buttons with
    `isEnabled()`. Teardown parses the real `add-*` shape
    (`{status, mensaje, <entity>_hash}`, no `data`/`company_hash`) (LL-017).
12. **Probe & freeze the live RESPONSE shape** before asserting on its fields, and
    let the ORCHESTRATOR run long gates in foreground (LL-009, LL-016).
13. **Date/datepicker inputs are locale-formatted, not ISO — and often readonly.** A
    date input renders in the app's configured locale/date format (e.g. `dd/MM/yyyy`)
    while the API is ISO (`yyyy-MM-dd`) — read the app's date config and CONVERT
    before asserting; never compare raw ISO to the rendered value. A readonly
    datepicker can't be `.fill()`ed → treat it OBSERVE-ONLY (assert pre-load, don't
    edit) unless the value must change, then drive the picker (LL-020).
14. **Load the STACK PROFILE before writing selectors** —
    `.claude/stack-profiles/${stack.frontend.framework}.md` → "E2E mechanics" holds the
    framework specifics (selector idiom, how to drive selects/pickers, how a hidden
    permission-gated control manifests, paginator/overlay quirks). The rules above are
    the universal pattern; the profile supplies the mechanics. If the profile lacks an
    "E2E mechanics" section, derive it from the code and propose adding it there.
15. **Run `verify-output` before returning**.
