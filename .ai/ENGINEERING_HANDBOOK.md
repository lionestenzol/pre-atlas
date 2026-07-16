# Engineering Handbook

> Single-document extract of Pre Atlas engineering rules.
> Usable as: ChatGPT system prompt, Cursor rules, Copilot instructions, or human onboarding doc.
> For the full split-file version, see the `.ai/rules/` and `.ai/lang/` directories.

---

## 1. Assemble First, Don't Generate

The default build posture is **assembler, not generator**. Before writing any non-trivial implementation, ask: is this a solved category?

If yes, search the ecosystem for the mature, maintained package. Surface what you found by name before generating any implementation. Never present a hand-rolled implementation and an established library as equivalent options.

**Hand-roll only when:**
1. No mature option exists for the capability
2. Integration depth IS the product value -- the library would make the product *worse*, not just *later*

**The discriminator:** "If I use the library instead, will the final product be worse, or just finished sooner?" Worse = write it yourself. Just sooner = use the library.

**Solved categories** (non-exhaustive): graph layout (cytoscape, vis-network, react-flow), drag-and-drop (sortablejs, dnd-kit), state machines (xstate), parsing (cheerio, babel), date/time (date-fns, dayjs), fuzzy search (fuse.js), validation (zod, pydantic), queuing (bullmq, celery), scheduling (node-cron), forms (react-hook-form), diffing (jsdiff), HTTP framework (express, fastapi, hono), ORM (prisma, sqlalchemy), logging (pino, loguru), caching (lru-cache), CLI (click, commander).

---

## 2. Code = Furniture

Every piece of code we keep is furniture in the house. We don't leave broken furniture in the house. We don't throw furniture out either. If something is broken, we fix it.

Documenting a bug is NOT fixing it. Adding a "known issue" caveat without a code fix is not acceptable.

**Decision tree:**
- Is the code ours/vendored/in-repo? YES = fix it now, inline
- Is the code external? File upstream + add a local workaround
- Is the cost-to-fix > value-of-keeping? YES = file deferral with date + owner + criteria. NO = fix it now

**What "fix" looks like:** replace bad path with clear error/throw, rewrite correctly, dedupe deps, guard unsafe assumptions, patch boilerplate, replace outdated API calls.

**What "fix" doesn't look like:** "Documented in Caveats." / "It's in a dead path." / "Upstream's problem." / "We'll come back to it."

---

## 3. Verify Before Verdict

A load-bearing claim about an external tool, library, or API is NOT sayable until it has been checked this session.

**Hard gates:**
1. Zero-research verdict = invalid verdict. Confidence is not a substitute for checking.
2. "X can't do Y" / "X is only Z" / "X doesn't fit" are factual claims. Cite them or don't make them.
3. Never construct an either/or between existing work and a proposed tool without checking whether they compose. Most tools compose.
4. The user's diagnosis of their own system outranks yours. They live in it.
5. When the user repeats or escalates, that is a signal you failed to CHECK something, not a signal to re-explain.

**The asymmetry:** researching a library first costs ~5 minutes. A wrong verdict kills a correct idea or sends a build down the wrong road for weeks.

---

## 4. No Building Without Locked Plan

LAW: no code until WHAT (the concrete artifact/outcome) and WHY (the goal it serves) are written and locked. Plan to the end -- the whole path to done, not the next poke. Search before building is mandatory.

---

## 5. Coding Style

### Immutability (Critical)
Always create new objects, never mutate existing ones. Immutable data prevents hidden side effects, makes debugging easier, and enables safe concurrency.

### File Organization
Many small files > few large files. High cohesion, low coupling. 200-400 lines typical, 800 max. Organize by feature/domain, not by type.

### Error Handling
Handle errors explicitly at every level. Provide user-friendly messages in UI. Log detailed context server-side. Never silently swallow errors.

### Input Validation
Validate at system boundaries (user input, external APIs, file content). Use schema-based validation (Zod, Pydantic). Fail fast with clear messages.

### Comments
Default to writing no comments. Only add one when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug. Never explain WHAT -- well-named identifiers do that. Never reference the current task or callers.

### Quality Checklist
- [ ] Code is readable and well-named
- [ ] Functions are small (<50 lines)
- [ ] Files are focused (<800 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Proper error handling
- [ ] No hardcoded values (use constants or config)
- [ ] No mutation (immutable patterns used)

---

## 6. Code Review

### When to Review
- After writing or modifying code
- Before any commit to shared branches
- When security-sensitive code is changed
- When architectural changes are made

### Severity Levels
| Level | Action |
|-------|--------|
| CRITICAL | BLOCK -- must fix before merge |
| HIGH | WARN -- should fix before merge |
| MEDIUM | INFO -- consider fixing |
| LOW | NOTE -- optional |

### Security Review Triggers
STOP and do a security review when touching: authentication/authorization, user input handling, database queries, file system operations, external API calls, cryptographic operations, payment/financial code.

### Common Issues to Catch
- **Security:** hardcoded credentials, SQL injection, XSS, path traversal, CSRF, auth bypasses
- **Quality:** large functions (>50 lines), large files (>800 lines), deep nesting (>4 levels), missing error handling, mutation
- **Performance:** N+1 queries, missing pagination, unbounded queries, missing caching

---

## 7. Development Workflow

1. **Research and Reuse** -- solved-category check FIRST. Search registries. Check docs. Prefer adopting a proven approach over writing net-new code.
2. **Plan First** -- generate plan before coding. Identify dependencies and risks. Break down into phases.
3. **TDD Approach** -- write tests first (RED), implement to pass (GREEN), refactor (IMPROVE), verify 80%+ coverage.
4. **Code Review** -- review immediately after writing code. Address CRITICAL and HIGH issues.
5. **Commit and Push** -- detailed commit messages, conventional commits format.

---

## 8. Git Workflow

### Commit Format
```
<type>: <description>

<optional body>
```
Types: feat, fix, refactor, docs, test, chore, perf, ci.

### PR Workflow
1. Analyze full commit history (not just latest commit)
2. Use `git diff [base-branch]...HEAD` to see all changes
3. Draft comprehensive PR summary with test plan

---

## 9. Security

### Pre-Commit Checklist
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitized HTML)
- [ ] CSRF protection enabled
- [ ] Authentication/authorization verified
- [ ] Rate limiting on all endpoints
- [ ] Error messages don't leak sensitive data

### Secret Management
- NEVER hardcode secrets in source code
- ALWAYS use environment variables or a secret manager
- Validate that required secrets are present at startup
- Rotate any secrets that may have been exposed

### Test Fixtures
Build test strings that resemble API keys via string concatenation (`.join()`), not literals. Push protection blocks literal key-shaped strings.

### Git Safety
- Never push to repositories you don't own (own fork fine, third-party upstream never)
- Review what's staged before committing
- Exclude submodules from bulk `git add`

---

## 10. Testing

### Minimum Coverage: 80%

### Test Types (all required)
1. **Unit Tests** -- individual functions, utilities, components
2. **Integration Tests** -- API endpoints, database operations (hit real databases, not mocks)
3. **E2E Tests** -- critical user flows

### TDD Workflow
1. Write test first (RED)
2. Run test -- it should FAIL
3. Write minimal implementation (GREEN)
4. Run test -- it should PASS
5. Refactor (IMPROVE)
6. Verify coverage (80%+)

### What Not to Test
- Private implementation details
- Framework internals
- Third-party library behavior
- Trivial getters/setters

---

## 11. Common Patterns

### Repository Pattern
Encapsulate data access behind a consistent interface (findAll, findById, create, update, delete). Business logic depends on the interface, not storage details.

### API Response Envelope
```json
{
  "success": true,
  "data": { },
  "error": null,
  "meta": { "total": 100, "page": 1, "limit": 20 }
}
```

### Ship Small, Iterate Fast
- Smallest real output first -- prove the concept before scaling
- Ship the loop, not the form -- get feedback running before polishing
- Progressive disclosure over instant complexity
- Projects have shapes -- respect natural structure

---

## Appendix: Language-Specific Rules

### Python
- PEP 8, type annotations on all function signatures
- Prefer `@dataclass(frozen=True)` and `NamedTuple` for immutability
- Formatting: black + isort + ruff
- Validation: Pydantic
- Catch specific exceptions first; chain with `from e`

### TypeScript/JavaScript
- `interface` for extensible object shapes; `type` for unions/intersections
- Avoid `any` -- use `unknown` and narrow safely
- React: named prop interfaces, no `React.FC`
- Validation: Zod with `z.infer<>`
- Immutability via spread + `Readonly<>`
- No `console.log` in production

### Wasp
- `main.wasp` is the single source of truth; `.wasp/` is generated (never edit)
- `.env.server` never committed; client vars use `REACT_APP_` prefix
- Operations: queries = read, actions = write; always check `context.user`
- Entity access via `context.entities.ModelName`, not raw Prisma
- Test with Vitest + @testing-library/react + msw; never run `wasp test` and `wasp start` simultaneously
- PostgreSQL required in production

---

*Extracted from Pre Atlas project rules. Provider-neutral.*
*Last updated: 2026-07-15.*
