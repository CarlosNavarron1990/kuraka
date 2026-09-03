---
name: analyze-testability
description: "Analyze source code to determine what tests are needed. Identifies public API, dependencies to mock, test categories (happy / error / edge), and coverage strategy."
agent: "`test-engineer`"
phase: "6 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Analyze Testability

Analyze a source file to produce a test plan before writing any tests,
for the project described in `kuraka.config.yaml`.

## Input

A source file path (relative to the project root, typically under
`${architecture.paths.backend_root}` or `${architecture.paths.frontend_root}`).

## Steps

### 1. Read and understand

Read the entire source file. For each public function / method, extract:

- Function signature (name, params, return type).
- Dependencies (what it imports / calls).
- Side effects (DB writes, API calls, file I/O).
- Error conditions (what raises exceptions).
- Business rules (status checks, validations).

### 2. Classify dependencies and pick mock strategy

The mock strategy depends on the stack and the dependency type. Consult
the stack profile for `${stack.backend.framework}` (or frontend) for the
framework-specific mocking idioms. Generic guidance:

| Dependency type | Mock strategy |
|---|---|
| Data-access functions (repositories) | Mock at the import boundary |
| Other services | Mock at the import boundary |
| External clients (HTTP, LLM, queue) | Mock the client wrapper |
| File system | Mock or use temp directories |
| DB session | Use real session for integration tests; mock for unit |

For project-specific available fixtures, consult
`.claude/project/conventions/test-fixtures.md` if maintained.

### 3. Generate test matrix

For each public function, produce:

```markdown
| Function | Test Case | Type | Category | Priority |
|----------|-----------|------|----------|----------|
| create_x | valid data → returns entity | Unit | Happy | P0 |
| create_x | duplicate → raises 409 | Unit | Error | P0 |
| process | wrong status → raises 400 | Unit | Error | P1 |
| get_results | empty results → returns empty list | Unit | Edge | P2 |
```

### 4. Determine test type

- **Unit test** if: function has mockable dependencies, no real DB
  needed.
- **Integration test** if: tests cross-module behavior, needs real DB.
- **Endpoint / route test** if: testing the HTTP / framework layer
  (status codes, response format).

### 5. Output: test plan

```markdown
## Test Plan: {filename}

### Public API (N functions)
1. `function_name(params)` → return_type

### Dependencies to Mock
- {module}.{method}
- {external_service}.{call}

### Test Matrix
| # | Function | Test Name | Category | Mocks |
|---|----------|-----------|----------|-------|

### Files to Create
- `${architecture.paths.tests_root}/unit/{module}/test_{name}.<ext>`

### Estimated Tests: N
```

The file extension and naming come from the stack profile's test
conventions.
