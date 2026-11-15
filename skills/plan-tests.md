---
name: plan-tests
description: "Pre-implementation test planning. Produces a test plan from stories BEFORE code is written. Defines what to test, fixtures needed, mocks, edge cases, and testability constraints that the developer must respect."
agent: "`test-engineer`"
phase: "2.5 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Plan Tests (Pre-Implementation)

Produce a test plan from approved stories BEFORE implementation begins.
This plan serves as a contract: the developer must write code that is
testable according to this plan.

## Difference from `analyze-testability`

| | `plan-tests` (Phase 2.5) | `analyze-testability` (Phase 6) |
|---|---|---|
| **Input** | Stories (no code yet) | Implemented source files |
| **Purpose** | Define testability constraints upfront | Analyze existing code for test gaps |
| **Output** | Test plan with expected signatures | Test matrix with mock strategies |
| **When** | Before implementation | After implementation |

## Input

- Approved story files from Phase 2.
- Frozen schema from Phase 3 (if available).
- Stack profile for `${stack.backend.framework}` — for the test framework
  conventions and per-layer test patterns.
- `.claude/project/conventions/test-fixtures.md` if present — catalog
  of fixtures available in this project's codebase.

## Steps

### 1. Extract testable units from stories

For each story, identify:

- **Service functions** described in the story (with expected signature).
- **Repository / data-access functions** implied by data access needs.
- **Endpoint routes** with expected status codes.
- **Business rules** that MUST have test coverage.

### 2. Define testability constraints

List constraints the developer must respect for the code to be testable:

```markdown
### Testability Constraints

1. `{service_function}` must accept `{dependency}` as injectable
   parameter (not instantiate internally) — needed for mocking.
2. `{business_rule}` must be in a separate function (not inline in the
   orchestrator) — needed for unit testing in isolation.
3. Side effects (DB writes, API calls) must go through repository /
   client interfaces — needed for mocking without touching real
   resources.
```

### 3. Plan test cases with their ORACLE (pre-implementation)

Every case carries its **oracle**: the concrete input, the concrete expected
result (return value / HTTP status + body fields / DB state / error), and the
**source** that fixes that value (AC id, REQ section, frozen-contract line,
business rule). The expected value comes from the SPEC, never from the code —
a test whose expectation is read off the implementation confirms whatever the
code does, bugs included, and mutation testing cannot catch that (it proves
the test is sensitive, not that the expectation is right).

```markdown
### Test Plan

| # | Story | Function / endpoint | Case | Input | Expected (oracle) | Source | Kind | Category |
|---|-------|---------------------|------|-------|-------------------|--------|------|----------|
| 1 | S1 | POST /resources | valid data | `{name:"A", qty:2}` | 201, body `id` set, row `resources(name='A', qty=2)` | AC-1 | ACCEPTANCE | Happy |
| 2 | S1 | POST /resources | duplicate name | same body twice | 2nd → 409 `code=DUPLICATE`, still 1 row | AC-2, REQ §4 | ACCEPTANCE | Error |
| 3 | S1 | normalize_name() | trailing spaces | `" A "` | `"A"` | rule R-3 | INTERNAL | Edge |
```

- **Kind**: `ACCEPTANCE` = contract / endpoint / AC-level behavior → written
  RED before any code (Phase 3.95, `test-engineer` TEST_FIRST) and locked.
  `INTERNAL` = helpers whose interface does not exist yet → written after
  implementation (Phase 6), still with a sourced expectation + mutation proof.
- **Size:** `ACCEPTANCE` rows carry the full oracle. `INTERNAL` rows are one
  line (`function · behavior · source`, Input/Expected = `—`): their concrete
  inputs are written in Phase 6 against the real interface. Plan budget by
  cycle size: S ≤80 · M ≤200 · L ≤350 lines; ≤3 acceptance cases per AC unless
  the AC itself enumerates more.
- **A case without a sourced expected value is incomplete.** If the spec does
  not determine the value (which status? rounding? what if empty?), it is an
  open question for the user (GATE0), never a guess and never "whatever the
  code returns".

### 4. Define required fixtures

```markdown
### Fixtures Needed

| Fixture | Source | Purpose |
|---------|--------|---------|
| `db_session` | conftest.py (exists) | Transaction-scoped DB session |
| `mock_{service}` | Create in test file | Mock for {service} dependency |
| `sample_{entity}` | Create in conftest or test | Test data factory |
```

Source values come from `.claude/project/conventions/test-fixtures.md` (if
maintained) and the project's `conftest.py` (or equivalent).

### 5. Identify risks to testability

Flag any story element that may be hard to test:

```markdown
### Testability Risks

| Risk | Story | Impact | Mitigation |
|------|-------|--------|------------|
| External API call in service | S2 | Can't unit test without mock | Developer must inject client |
| File I/O in handler | S3 | Needs temp files in test | Use in-memory mock |
| Async concurrency logic | S1 | Hard to test concurrency | Test sequential behavior, mock synchronization |
```

### 6. Recorrido table (user-visible changes only)

If the change is visible to the user, the plan includes a `## Recorrido`
section — the contract the `recorrido-e2e` skill EXECUTES in a real browser
at Phase 6.8 (the tester runs it, never designs it):

```markdown
## Recorrido

| # | AC | User action | Expected UI | Expected backend effect (exact endpoint/query) | Evidence |
|---|----|-------------|-------------|------------------------------------------------|----------|
| 1 | AC-1 | … | … | `GET /api/…` → field `x == …` / `SELECT … WHERE …` | screenshot + response |
| n | outcome | … | … | … | … |
```

One row per acceptance criterion; the LAST row proves the cycle's outcome
sentence. Every row names the exact endpoint or query and the fields to check;
a row with no backend effect is marked `UI-ONLY` with its reason (it counts as
partial evidence). A user-visible change whose plan has no Recorrido table is
returned by the tester as `RECORRIDO SIN TABLA` — rework you avoid here.

## Output

Create a test plan file at:
`${architecture.paths.docs_process_root}/test-plans/TEST-PLAN-{ticket}.md`

```markdown
# Test Plan: {ticket}

## Stories Covered
- S1: {title}
- S2: {title}

## Excluded Categories
(from Out of Scope sections of each story — these tests are NOT included)

## Testability Constraints
[from step 2]

## Test Cases
[from step 3]

## Fixtures
[from step 4]

## Testability Risks
[from step 5]

## Recorrido
[from step 6 — only for user-visible changes]

## Estimated Test Count: N
- Unit: N
- Integration: N
- Endpoint: N

## Files to Create
- `${architecture.paths.tests_root}/unit/{module}/test_{name}.<ext>`
- `${architecture.paths.tests_root}/integration/test_{name}.<ext>`
```

## Rules

1. **No implementation details** — plan based on stories and expected
   interfaces, not code.
2. **Every business rule in AC must have at least one test case** — if a
   rule is untestable, flag it.
3. **Prefer injectable dependencies** — flag any story that implies tight
   coupling.
4. **Happy + Error + Edge for every public function** — 3 cases per function
   is the floor AND the default; add more only for a rule the AC enumerates.
5. **The developer reads this plan** — write it as a contract, not a
   suggestion.
6. **Every case has an oracle with a source** (step 3). No source → open
   question, not a test case.
7. **Mark ACCEPTANCE vs INTERNAL** — acceptance cases become the locked red
   tests of Phase 3.95; the developer may not edit them.
6. **Respect Out of Scope** — never include test cases for items the
   story explicitly excluded. See `LL-004` in the project's lessons-learned
   if present.
7. **Plan a full-contract assertion** — for any function returning a contract
   consumed elsewhere, the plan must require asserting every consumer-used field
   (especially secrets/tokens/ids), not just the happy subset.
8. **Plan ≥1 live-path case + captured-payload fixture** for every external
   client / endpoint / webhook — never plan only mocked-happy cases against a
   described contract.
9. **Shared-DB hygiene** — plan delta/`>=` assertions, never absolute row counts;
   for WRITE surfaces plan the apply happy-path + idempotency test in Phase 4 so
   "green" exercises the new behavior.
