---
name: review-implementation
description: "Code review after implementation. Uses 6D framework: correctness, security, performance, maintainability, readability, tests. Used in Phase 5."
agent: "`code-reviewer`"
phase: "5 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Review Implementation

You are executing the Code Review skill (Phase 5 of the workflow) for
the project described in `kuraka.config.yaml`.

## Input

Implemented code from Phase 4. The user may point to specific files, or
you review all changed files.

## Steps

### 1. Identify changed files

```bash
git diff --name-only HEAD~N  # or compare against the main branch
```

Or review the files listed in the story files.

### 2. Load context

Per the `code-reviewer` agent's Context section:

- `kuraka.config.yaml` for paths, layers, conventions, size limits.
- Stack profile(s) for stack-specific architecture invariants.
- `.claude/project/review-checks/code-reviewer.md` for project-specific
  checks (run these in addition to the generic checklist).
- `.claude/project/lessons-learned/*.md` filtered by `applies_to`.

### 3. Apply 6D framework

#### D1: Correctness
- Null / undefined handling in critical paths.
- Edge cases: empty lists, zero values, null dates.
- Off-by-one errors in loops / pagination.
- Error propagation (no swallowed exceptions).

#### D2: Security
- Injection (parameterized queries?).
- Tenant isolation (when `conventions.multi_tenant: true`, all queries
  filter by `conventions.tenant_column_name`?).
- Auth on all endpoints.
- No secrets in code.
- No data leaks in error responses.

#### D3: Performance
- N+1 queries in loops.
- Missing DB indexes on filtered / sorted columns.
- Large result sets without pagination.
- Blocking operations in async code.

#### D4: Maintainability
- File size within `conventions.max_file_loc`.
- Function size within `conventions.max_function_loc`.
- No code duplication (DRY).
- Single responsibility per class / function.
- No circular dependencies.

#### D5: Readability
- Descriptive names (min 3 chars).
- Early returns (no pyramid nesting > 3 levels).
- No commented-out code.
- Import order per the stack profile's idiom.

#### D6: Tests
- Happy path covered.
- Error cases covered.
- Edge cases covered.
- AAA pattern used.
- Proper mocking (no real DB / external APIs in unit tests).

### 4. Architecture compliance

Apply every architecture invariant from the stack profile for
`${stack.backend.framework}` (and frontend if applicable). Common
universal checks:

- All imports at file top.
- No commented-out code.
- No `console.log` / `print` for production output.
- Null syntax respected.

Stack-specific checks (e.g., for FastAPI: no try/except in endpoints, no
`db.query()` in services, no layer skipping) come from the profile.

### 5. Project-specific checks

Apply every check in `.claude/project/review-checks/code-reviewer.md`
if it exists.

### 5.5 Directed checks (run EVERY time — see `code-reviewer` agent for the full list)

Default checks, not opt-in:

- **Contract cross-check** — implemented request/response bodies vs frozen schema
  + verbatim payloads, on field name, type, id-vs-hash, casing, serialization
  format. Mismatch = BLOCKER-adjacent.
- **Normalize-before-compare** — external strings used as keys/match targets are
  normalized idempotently.
- **Single-submit guard**, **design tokens defined**, **namespace type-imports**,
  **sibling-guard parity**, **silent deviation**, **re-derive every number**.

Use the **DEFERRED** severity for real gaps a later planned phase owns (e.g.
Phase-6 tests) — never inflate them to BLOCKER. If a reviewer digest was passed
(rules/17 T8), review against it instead of re-reading the whole surface.

### 6. Run verification

```bash
${stack.backend.lint_cmd}
${stack.backend.test_cmd}
```

(Frontend equivalents if reviewing frontend code.)

### 7. Output

Produce a review report with verdict and findings table, following the
format in the `code-reviewer` agent definition.
