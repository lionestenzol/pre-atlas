# Testing Requirements

## Minimum Test Coverage: 80%

Test types (ALL required where applicable):
1. **Unit Tests** — individual functions, utilities, components
2. **Integration Tests** — API endpoints, database operations
3. **E2E Tests** — critical user flows

## Test-Driven Development (mandatory workflow)

1. Write test first (RED) — the test defines the expected behavior
2. Run test — it should FAIL (proves the test is meaningful)
3. Write minimal implementation (GREEN) — just enough to pass
4. Run test — it should PASS
5. Refactor (IMPROVE) — clean up without breaking tests
6. Verify coverage (80%+)

## Troubleshooting Test Failures

1. Check test isolation — tests should not depend on each other
2. Verify mocks are correct — mocks should match real behavior
3. Fix implementation, not tests (unless tests are wrong)
4. Integration tests should hit real databases, not mocks (prior incident: mock/prod divergence masked a broken migration)

## What to Test

- Business logic and domain rules
- Edge cases and error paths
- User interactions (form submission, button clicks)
- Error states (operation failures, auth redirects)
- Data transformations and validations

## What Not to Test

- Framework internals (trust the framework)
- Simple getters/setters with no logic
- Third-party library behavior (test your integration, not theirs)
- UI layout details (unless layout IS the feature)
