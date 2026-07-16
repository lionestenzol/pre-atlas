# Security Guidelines

## Mandatory Security Checks

Before ANY commit:
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitized HTML)
- [ ] CSRF protection enabled
- [ ] Authentication/authorization verified
- [ ] Rate limiting on all endpoints
- [ ] Error messages don't leak sensitive data

## Secret Management

- NEVER hardcode secrets in source code
- ALWAYS use environment variables or a secret manager
- Validate that required secrets are present at startup
- Rotate any secrets that may have been exposed
- Test fixtures that look like real API keys must be built via string concatenation, not literals (push protection will block key-shaped strings)

## Security Response Protocol

If security issue found:
1. STOP immediately
2. Perform security review of the affected area
3. Fix CRITICAL issues before continuing
4. Rotate any exposed secrets
5. Review entire codebase for similar issues

## OWASP Top 10 Awareness

1. **Injection** — parameterize all queries, never concatenate user input
2. **Broken Authentication** — use proven auth libraries, enforce session management
3. **Sensitive Data Exposure** — encrypt at rest and in transit, minimize data collection
4. **XML External Entities** — disable external entity processing
5. **Broken Access Control** — check authorization on every request, deny by default
6. **Security Misconfiguration** — remove defaults, disable unnecessary features
7. **Cross-Site Scripting** — escape output, use CSP headers
8. **Insecure Deserialization** — validate and sanitize serialized data
9. **Using Components with Known Vulnerabilities** — keep dependencies updated
10. **Insufficient Logging** — log security events, monitor for anomalies

## Git Safety

- Never push to repositories you don't own (your own fork is fine)
- Never force-push to main/master
- Never skip pre-commit hooks unless explicitly asked
- Always review staged changes before pushing
