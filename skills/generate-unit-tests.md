---
name: generate-unit-tests
description: "Generate unit tests for services, repositories, and models. Uses the project's test framework with AAA pattern, mocks dependencies, follows the stack profile's conventions."
agent: "`test-engineer`"
phase: "6 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Generate Unit Tests

Create unit tests from a test plan produced by `analyze-testability`,
for the project described in `kuraka.config.yaml`.

## Input

- Test plan (from `analyze-testability`).
- Source file to test.

## Steps

### 1. Pick the framework template

Consult the stack profile for `${stack.backend.framework}` (or frontend
for frontend tests). The profile's "Test patterns" section documents the
framework's idiomatic test structure (e.g., pytest with AAA + class-based
grouping for Python; Vitest with `describe` + `it` for TypeScript).

### 2. Mirror the source layout

Create the test file under `${architecture.paths.tests_root}/` mirroring
the source path one-for-one. File naming follows the stack profile's
convention (e.g., `test_{name}.py` for pytest, `{name}.spec.ts` for
Vitest/Jest).

### 3. Apply AAA pattern (Arrange / Act / Assert)

Universal — every test has three clearly-separated sections (comments
or blank lines). Naming is declarative —
`test_should_{action}_when_{condition}` for pytest, or the framework's
idiomatic form.

### 4. Rules for service-layer tests

1. Mock data-access dependencies — services never touch real DB in unit
   tests.
2. Mock other services — test in isolation.
3. Test state transitions — verify status changes.
4. Test validation — verify the expected error type is raised for
   invalid inputs.
5. Test not-found — verify the expected error type is raised when an
   entity is missing.
6. Return value assertions — verify the function returns expected data.

### 5. Rules for data-access (repository) tests

1. Use the project's DB session fixture (from
   `.claude/project/conventions/test-fixtures.md` if maintained, or
   `conftest.py` equivalent) — real DB with auto-rollback.
2. Create test data in Arrange.
3. Test CRUD operations.
4. Test tenant isolation when `conventions.multi_tenant: true` — same
   ID, different tenant → not found.
5. Test pagination.
6. Test constraints — unique violations, FK constraints.

### 6. Rules for model tests

1. No DB queries — test schema metadata only.
2. Verify columns exist.
3. Verify FK targets.
4. Verify constraints (unique, check, not-null).
5. Verify relationships (if defined).

### 7. Build test data with helpers

Use a `_make_*()` pattern for test data builders. Keep them in the test
file or under a `tests/builders/` module if shared.

```python
# Python pytest example (for python-fastapi profile)
def _make_mock_entity(id: int = 1, tenant_id: int = 1, **overrides):
    entity = MagicMock()
    entity.id = id
    entity.tenant_id = tenant_id
    for key, value in overrides.items():
        setattr(entity, key, value)
    return entity
```

```typescript
// TypeScript Vitest example (for vue-pinia profile)
function makeMockEntity(overrides: Partial<Entity> = {}): Entity {
  return {
    id: 1,
    tenantId: 1,
    ...overrides,
  }
}
```

For more framework-specific examples, consult the stack profile.

### 7b. Runner-only gotchas — load the STACK PROFILE first

A green build is NOT a green test run: every stack has gotchas that pass compilation and
fail only under the test runner (the date/locale adapter the spec must provide, i18n
directive stubs, template forms that throw only in JIT, guard resets between synthetic
submits). **These are framework-specific and live in
`.claude/stack-profiles/${stack.frontend.framework}.md` (or the backend profile) under
"Test patterns" — read it before writing component tests.** If you hit a gotcha that
isn't documented there, propose adding it to the profile instead of re-deriving it in
each spec.

Universal (any stack):
1. **Decimals often serialize as strings** → compare with `Number()`, never `.toBe(str)`.
2. **Test-vs-code reconciliation:** if a failing test encodes a KNOWN-bug premise the code
   has since fixed on purpose (confirm via comment/story/commit), UPDATE the test to the
   fixed contract — never weaken the code to satisfy a stale test (LL-019).

### 8. After writing

1. Run `${stack.backend.lint_cmd}` (or frontend equivalent) on the test
   file.
2. Run the new test alone using the framework's idiom (e.g.,
   `pytest path/to/test_file.py -v`, `vitest run path/to/file.spec.ts`).
3. Run `${stack.backend.test_cmd}` to verify the full suite still passes.
   **Gate integrity:** run WITHOUT a pipe; assert exit 0 AND absence of "FAILED" AND
   that the runner executed the FULL count (browser runners: `Executed N of N
   (SUCCESS)`) — a DISCONNECT mid-run gives a PARTIAL tally that is not a pass;
   re-run to completion (LL-019).
