# Development Workflow

The full feature implementation pipeline: research, planning, TDD, code review, then commit.

## Step 0: Research and Reuse (mandatory)

Before writing any new implementation:

1. **Solved-category check FIRST** — is this a solved category (graph layout, drag-drop, FSM, parsing, dates, fuzzy search, validation, queuing, scheduling, forms, timelines, etc.)? If yes, see `assemble-first.md` — the library option must be named explicitly before any hand-roll is considered, AND the "worse vs later" discriminator must pass before a hand-roll is accepted.

2. **Search existing code** — look for existing implementations, templates, and patterns in the codebase and on GitHub before writing anything new.

3. **Check library docs** — confirm API behavior, package usage, and version-specific details before implementing.

4. **Check package registries** — search npm, PyPI, crates.io, etc. before writing utility code. Prefer battle-tested libraries over hand-rolled solutions.

5. **Search for adaptable implementations** — look for open-source projects that solve 80%+ of the problem and can be forked, ported, or wrapped.

Prefer adopting or porting a proven approach over writing net-new code when it meets the requirement.

## Step 1: Plan First

- Create an implementation plan before coding
- Generate planning docs: PRD, architecture, system design, tech doc, task list
- Identify dependencies and risks
- Break down into phases
- **LAW: No building without a locked plan** — WHAT + WHY + plan to the end before any code

## Step 2: TDD Approach

- Write tests first (RED)
- Implement to pass tests (GREEN)
- Refactor (IMPROVE)
- Verify 80%+ coverage

## Step 3: Code Review

- Review code immediately after writing
- Address CRITICAL and HIGH issues
- Fix MEDIUM issues when possible

## Step 4: Commit and Push

- Detailed commit messages
- Follow conventional commits format (see `git-workflow.md`)
- One logical change per commit

## Step 5: Pre-Review Checks

- Verify all automated checks (CI/CD) are passing
- Resolve any merge conflicts
- Ensure branch is up to date with target branch
- Only request review after these checks pass
