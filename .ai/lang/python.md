# Python Coding Style

Extends the universal rules in `../rules/coding-style.md` with Python-specific conventions.

## Standards

- Follow **PEP 8** conventions
- Use **type annotations** on all function signatures
- Default to writing no comments (see `../rules/coding-style.md`)

## Immutability

Prefer immutable data structures:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str
    email: str

from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
```

## Formatting

- **black** for code formatting
- **isort** for import sorting
- **ruff** for linting

## Error Handling

```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error("Operation failed: %s", e)
    raise
except Exception as e:
    logger.error("Unexpected error: %s", e)
    raise RuntimeError("Operation failed") from e
```

- Always catch specific exceptions first
- Use `from e` to chain exceptions (preserve traceback)
- Never bare `except:` without re-raising

## Input Validation

Use Pydantic for schema-based validation:

```python
from pydantic import BaseModel, EmailStr

class UserInput(BaseModel):
    email: EmailStr
    age: int = Field(ge=0, le=150)

validated = UserInput.model_validate(raw_input)
```

## File Organization

- Organize by feature/domain, not by type
- `__init__.py` should be minimal (re-exports only)
- Keep modules under 400 lines; extract when approaching 800
