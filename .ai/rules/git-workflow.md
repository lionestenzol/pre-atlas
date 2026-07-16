# Git Workflow

## Commit Message Format

```
<type>: <description>

<optional body>
```

**Types:** feat, fix, refactor, docs, test, chore, perf, ci

Examples:
- `feat: add user authentication flow`
- `fix: resolve race condition in job queue`
- `refactor: extract validation into shared module`
- `docs: update API endpoint documentation`
- `test: add integration tests for payment flow`

## Commit Discipline

- One logical change per commit
- Commit messages explain WHY, not WHAT (the diff shows WHAT)
- Never commit secrets, credentials, or API keys
- Never commit debug/console.log statements
- Review `git status` before committing — check for unintended files

## Pull Request Workflow

When creating PRs:
1. Analyze full commit history (not just latest commit)
2. Use `git diff <base-branch>...HEAD` to see all changes
3. Draft comprehensive PR summary
4. Include test plan with verification steps
5. Push with `-u` flag if new branch

## Branch Hygiene

- Feature branches from main
- Delete branches after merge
- Keep branches short-lived (days, not weeks)
- Rebase on main before PR when there are conflicts
