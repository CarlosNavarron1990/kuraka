---
name: generate-endpoint-tests
description: "Generate endpoint / route tests using the framework's HTTP test client. Tests HTTP status codes, response shapes, auth requirements, and error formats."
agent: "`test-engineer`"
phase: "6 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Generate Endpoint Tests

Create endpoint tests that verify HTTP behavior using the framework's
test client, for the project described in `kuraka.config.yaml`.

## Input

- Endpoint file to test (under `${architecture.paths.backend_root}`).
- Test plan from `analyze-testability`.

## Key Principle

Endpoint tests mock the **service layer** — they test HTTP handling,
not business logic.

```
Endpoint Test → mocks → Service
                         ↓ (not tested here)
                     Repository → DB
```

## Steps

### 1. Pick the framework's test client

Consult the stack profile for `${stack.backend.framework}`. The profile
documents:

- The HTTP test client to use (e.g., `TestClient` from FastAPI,
  `supertest` for Express, `Rails::ControllerTestCase` for Rails).
- The mocking idiom for the service layer.
- The fixtures available for auth / tenant context (see
  `.claude/project/conventions/test-fixtures.md` if maintained).

### 2. Test file location and naming

Under `${architecture.paths.tests_root}/`, mirroring the endpoint's
source path. Naming follows the stack profile's convention.

### 3. What to test per endpoint

| Method | Test Cases |
|--------|-----------|
| **POST** | 2xx on success, 401 no auth, 400 missing fields, 404 not found (if applicable) |
| **GET list** | 200 with items, 200 empty list, pagination params passed |
| **GET detail** | 200 found, 404 not found, tenant isolation (if `conventions.multi_tenant: true`) |
| **PUT / PATCH** | 200 updated, 404 not found, 400 invalid data |
| **DELETE** | 204 deleted, 404 not found |
| **Download / streaming** | 200 with correct content-type and content-disposition headers |

### 4. Auth tests

For every endpoint, test:

- 401 when no token / auth missing.
- 403 when token has the wrong role (if RBAC applies).

The auth mechanism is stack-specific — the stack profile documents how
to test it.

### 5. Response shape tests

For every endpoint that returns structured data:

- Verify required fields are present.
- Verify the response schema matches the API contract from the story.

### 6. Tenant isolation tests (when `conventions.multi_tenant: true`)

For every endpoint that reads tenant-scoped data:

- Test that a request from tenant A cannot access tenant B's data
  (returns 404 or 403, never 200).

### 7. Universal test rules

Same as `generate-unit-tests`:

- AAA pattern, declarative test names.
- Mock the service, not the repository.
- Use the framework's auth fixture (e.g., `auth_headers` for FastAPI,
  `loginAs(user)` for Rails).
- No hardcoded IDs — use fixtures or generated values.

### 8. After writing

1. Run `${stack.backend.lint_cmd}` on the test file.
2. Run the new tests alone, then run `${stack.backend.test_cmd}` for
   the full suite.

## Framework-specific templates

For concrete templates per framework, consult the stack profile. The
profile's "Test patterns" section shows the idiomatic structure.
