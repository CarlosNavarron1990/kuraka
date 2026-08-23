---
name: write-tests
description: "Write unit and integration tests for implemented functionality. Uses the project's test framework with AAA pattern. Used in Phase 6 of the workflow."
agent: "`backend-developer` or `frontend-developer`"
phase: "6 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Write Tests

You are executing the Test Writing skill (Phase 6 of the workflow) for
the project described in `kuraka.config.yaml`.

## Input

Implemented code from Phase 4 / 5. Review story files for required test
cases.

## Steps

### 1. Identify what needs tests

For each implemented file, map to its test file. The naming and location
come from the stack profile for `${stack.backend.framework}` (or
frontend equivalent). For example with `python-fastapi`:

| Source File | Test File | Type |
|-------------|-----------|------|
| `api/services/{module}/service.py` | `tests/unit/services/test_{service}.py` | Unit |
| `repositories/{module}/repo.py` | `tests/unit/repositories/test_{repo}.py` | Unit |
| `api/endpoints/{module}/endpoint.py` | `tests/integration/test_{endpoint}.py` | Integration |

### 2. Test structure (AAA pattern)

Apply the AAA pattern (Arrange / Act / Assert), clearly separated. The
test framework and idioms come from the stack profile.

Example for Python pytest (from the `python-fastapi` profile):

```python
"""Tests for {module} {layer}."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Fixtures live in conftest.py, not here


class TestServiceMethod:
    """Tests for ServiceClass.method_name."""

    def test_should_return_result_when_valid_input(self):
        # Arrange
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = expected_entity
        service = ServiceClass(mock_repo)

        # Act
        result = service.get_by_id(1)

        # Assert
        assert result.id == 1
        mock_repo.find_by_id.assert_called_once_with(1)

    def test_should_raise_not_found_when_id_missing(self):
        # Arrange
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        service = ServiceClass(mock_repo)

        # Act & Assert
        with pytest.raises(ErrNotFound):
            service.get_by_id(999)
```

For other stacks, consult the corresponding stack profile's "Test
patterns" section.

### 3. What to test

**MUST test:**

- Happy path (valid input → expected output).
- Error cases (not found, validation failure, auth denied).
- Edge cases (empty list, null values, zero, boundary values).
- Business logic transformations.
- Tenant isolation (when `conventions.multi_tenant: true`).

**DON'T test:**

- Framework internals (the stack profile lists what NOT to test).
- Simple getters / setters.
- Config files.
- Third-party libraries.

### 4. Mocking rules

- **Unit tests**: Mock repositories when testing services; mock DB when
  testing repositories.
- **Integration tests**: Use the framework's HTTP test client with a
  test DB.
- **Never mock**: The code under test itself.
- **Always mock**: External APIs, email, file system, queue brokers.

### 5. Run tests

```bash
${stack.backend.test_cmd}
```

Verify:

- All tests pass.
- No warnings about unclosed resources.
- `${stack.backend.lint_cmd}` still passes.

### 6. Report

- Tests created (count and files).
- All passing? Yes / No.
- Coverage notes (what's covered, what's not).
