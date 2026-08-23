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

### 3. Plan test cases (pre-implementation)

```markdown
### Test Plan

| # | Story | Function (expected) | Test Case | Type | Category |
|---|-------|---------------------|-----------|------|----------|
| 1 | S1 | create_resource() | valid data returns resource | Unit | Happy |
| 2 | S1 | create_resource() | duplicate raises 409 | Unit | Error |
| 3 | S1 | create_resource() | missing required field raises 400 | Unit | Edge |
```

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
4. **Happy + Error + Edge for every public function** — minimum 3 test
   cases per function.
5. **The developer reads this plan** — write it as a contract, not a
   suggestion.
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
