# Human Onboarding Guide

How to use these engineering rules without any AI assistant -- as a human developer joining the project.

## Quick Start

1. Read `ENGINEERING_HANDBOOK.md` in the `.ai/` directory. It is the single-document version of all project rules.
2. Read `DECISIONS.md` at the repo root. It contains 27 architectural decisions that explain WHY the system is shaped the way it is.
3. Read the language file in `.ai/lang/` that matches your stack (Python, TypeScript, or Wasp).

## The Three Laws

These are non-negotiable:

1. **Assemble first.** Before writing any non-trivial code, check if a library solves the problem. Surface the library by name. Only hand-roll if the library would make the product worse, not just later.

2. **Code = furniture.** If you find a bug, fix it. Don't document it and move on. Don't throw the code out either. Fix or defer with a date and owner.

3. **No building without a locked plan.** Write WHAT you're building and WHY before any code. Plan to the end, not the next poke.

## Development Checklist

Before starting work:
- [ ] Read the relevant area of DECISIONS.md
- [ ] Check if the task is in a solved category (see handbook section 1)
- [ ] Write a plan with WHAT and WHY

While coding:
- [ ] Immutable patterns (new objects, not mutations)
- [ ] Functions under 50 lines, files under 800 lines
- [ ] Error handling at every level
- [ ] Input validation at system boundaries

Before committing:
- [ ] No hardcoded secrets
- [ ] Tests written (80% coverage minimum)
- [ ] Security checklist passed (see handbook section 9)
- [ ] Conventional commit format: `type: description`

## Where to Find Things

| What | Where |
|------|-------|
| Engineering rules | `.ai/ENGINEERING_HANDBOOK.md` |
| Architecture decisions | `DECISIONS.md` |
| Python conventions | `.ai/lang/python.md` |
| TypeScript conventions | `.ai/lang/typescript.md` |
| Wasp conventions | `.ai/lang/wasp.md` |
| Project context | `CLAUDE.md` (also readable by humans) |
| Split rule files | `.ai/rules/*.md` |

## Commit Message Format

```
type: short description

Optional body explaining WHY, not WHAT.
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

## Integration Test Rule

Hit real databases in integration tests, not mocks. This project was burned by mock/prod divergence in the past.
