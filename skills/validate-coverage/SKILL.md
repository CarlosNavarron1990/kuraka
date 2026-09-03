---
name: validate-coverage
description: "Validate test coverage after generating tests. Runs lint + tests, identifies gaps, reports coverage metrics."
agent: "`test-engineer`"
phase: "6 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Validate Coverage

After generating tests, validate they pass and cover the required
scenarios, for the project described in `kuraka.config.yaml`.

## Steps

### 1. Lint check

```bash
${stack.backend.lint_cmd}    # or ${stack.frontend.lint_cmd} for frontend tests
```

Fix any issues before proceeding.

### 2. Run tests

```bash
# Run only the new test file (use the stack's single-file invocation idiom)
# e.g., pytest path/to/test_file.py -v   for pytest
#       vitest run path/to/file.spec.ts  for Vitest

# Run the full suite to check no regressions
${stack.backend.test_cmd}    # or frontend equivalent
```

### 3. Coverage analysis

Check what's covered vs what's missing. The layer names come from
`architecture.layers`. Example layout for a typical backend cycle:

| Layer | Must Cover | Check |
|-------|------------|-------|
| **Models** | Columns, FKs, constraints, tenant column (if multi-tenant) | Models test file |
| **Repositories / Data access** | CRUD, pagination, tenant isolation | Repository test files |
| **Services** | Business logic, state transitions, errors | Service test files |
| **Endpoints / Routes** | HTTP codes, auth, response shapes | Endpoint test files |

Frontend equivalent: types, services, stores, composables, components.

### 4. Gap report

For each source file, verify:

```markdown
| Source File | Test File | Tests | Happy | Error | Edge | Status |
|-------------|-----------|-------|-------|-------|------|--------|
| {path}      | {path}    | N     | N     | N     | N    | OK / GAPS |
```

### 5. Quality checklist

- [ ] All tests follow AAA pattern.
- [ ] Test names follow the stack profile's idiom (e.g.,
  `test_should_{action}_when_{condition}` for pytest).
- [ ] No untyped helpers in typed stacks.
- [ ] Mocks properly scoped (no leaking between tests).
- [ ] No hardcoded IDs (use fixtures / builders).
- [ ] Each test is independent (no order dependency).
- [ ] `${stack.*.lint_cmd}` passes on all test files.
- [ ] `${stack.*.test_cmd}` green (all tests pass, including existing).
- [ ] No `print` / `console.log` in tests (use the test framework's
  output capture).

### 6. Coverage targets

| Layer | Target |
|-------|--------|
| Services / business logic | 80% line coverage |
| Repositories / data access | 80% line coverage |
| Endpoints / routes | 90% route coverage |
| Models | 100% column / constraint coverage |

These are recommended defaults; the project may override in
`.claude/project/conventions/test-coverage.md` if it has stricter
targets.

### 7. Report

```markdown
## Coverage Report

**Tests written:** N
**Tests passing:** N
**Lint issues:** 0
**Regression:** None

### By Layer
| Layer | Files | Tests | Pass | Fail |
|-------|-------|-------|------|------|

### Gaps Identified
- [ ] Missing: error case for X
- [ ] Missing: edge case for Y
```
