# Code Review Standards

## When to Review

**Mandatory review triggers:**
- After writing or modifying code
- Before any commit to shared branches
- When security-sensitive code is changed (auth, payments, user data)
- When architectural changes are made
- Before merging pull requests

**Pre-review requirements:**
- All automated checks (CI/CD) passing
- Merge conflicts resolved
- Branch up to date with target branch

## Review Checklist

Before marking code complete:
- [ ] Code is readable and well-named
- [ ] Functions are focused (<50 lines)
- [ ] Files are cohesive (<800 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Errors are handled explicitly
- [ ] No hardcoded secrets or credentials
- [ ] No debug statements left in
- [ ] Tests exist for new functionality
- [ ] Test coverage meets 80% minimum

## Security Review Triggers

**STOP and do a security review when touching:**
- Authentication or authorization code
- User input handling
- Database queries
- File system operations
- External API calls
- Cryptographic operations
- Payment or financial code

## Review Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| CRITICAL | Security vulnerability or data loss risk | **BLOCK** - Must fix before merge |
| HIGH | Bug or significant quality issue | **WARN** - Should fix before merge |
| MEDIUM | Maintainability concern | **INFO** - Consider fixing |
| LOW | Style or minor suggestion | **NOTE** - Optional |

## Common Issues to Catch

### Security
- Hardcoded credentials (API keys, passwords, tokens)
- SQL injection (string concatenation in queries)
- XSS vulnerabilities (unescaped user input)
- Path traversal (unsanitized file paths)
- CSRF protection missing
- Authentication bypasses

### Code Quality
- Large functions (>50 lines) — split into smaller
- Large files (>800 lines) — extract modules
- Deep nesting (>4 levels) — use early returns
- Missing error handling — handle explicitly
- Mutation patterns — prefer immutable operations
- Missing tests — add test coverage

### Performance
- N+1 queries — use JOINs or batching
- Missing pagination — add LIMIT to queries
- Unbounded queries — add constraints
- Missing caching — cache expensive operations

## Approval Criteria

- **Approve**: No CRITICAL or HIGH issues
- **Warning**: Only HIGH issues (merge with caution)
- **Block**: CRITICAL issues found
