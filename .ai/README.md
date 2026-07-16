# .ai/ — Provider-Neutral Project Intelligence

This directory makes Pre Atlas's engineering rules, decisions, and context loadable by **any** AI coding assistant — Claude, ChatGPT, Gemini, Cursor, Copilot, or a human reading docs.

## Why this exists

Pre Atlas has 30+ engineering rules and 240+ decision records that currently live in Claude Code's proprietary memory system (`~/.claude/rules/`, `~/.claude/projects/.../memory/`). If Anthropic goes down, changes pricing, or a different tool becomes primary, all that accumulated intelligence is trapped.

This directory is **Plan B**: the same rules and decisions, in formats any tool can consume.

## Directory structure

```
.ai/
  README.md              # You are here
  rules/                 # Universal engineering rules (provider-neutral)
    assemble-first.md    # Use libraries for solved categories
    code-as-furniture.md # Fix bugs inline, never leave them
    code-review.md       # Review checklist and severity levels
    coding-style.md      # Immutability, file org, error handling
    development-workflow.md  # Research > Plan > TDD > Review > Commit
    git-workflow.md      # Conventional commits, PR process
    patterns.md          # Repository pattern, API response format
    security.md          # OWASP, secrets, pre-commit checks
    testing.md           # TDD workflow, 80% coverage minimum
    verify-before-verdict.md  # Research before asserting
  lang/                  # Language-specific extensions
    python.md            # PEP 8, type annotations, frozen dataclasses
    typescript.md        # Types, interfaces, Zod, React patterns
    wasp.md              # Wasp framework conventions and security
  providers/             # Ready-to-paste instructions per AI tool
    chatgpt.md           # ChatGPT custom instructions format
    gemini.md            # Gemini system prompt format
    cursor.md            # .cursorrules format
    human.md             # Human developer onboarding

DECISIONS.md             # (repo root) Load-bearing architectural decisions
ENGINEERING_HANDBOOK.md  # (repo root) All rules in one file
```

## How to use with each provider

### Claude Code (current primary)
Already loaded automatically via `~/.claude/rules/` and `CLAUDE.md`. The `.ai/` directory is the portable backup.

### ChatGPT (Custom GPT or API)
1. Copy `providers/chatgpt.md` into Custom Instructions or system prompt
2. For a Custom GPT, upload `ENGINEERING_HANDBOOK.md` + `DECISIONS.md` as knowledge files
3. For API usage, include `ENGINEERING_HANDBOOK.md` content in the system message

### Google Gemini
1. Copy `providers/gemini.md` into the system instruction field
2. Attach `ENGINEERING_HANDBOOK.md` and `DECISIONS.md` as context

### Cursor
1. Copy `providers/cursor.md` to `.cursorrules` at repo root
2. Cursor auto-loads it for every session in this project

### Copilot / Other
1. Use `ENGINEERING_HANDBOOK.md` as the context document
2. Reference specific rules from `rules/` as needed

### Human developer (no AI)
1. Read `providers/human.md` as your onboarding guide
2. `DECISIONS.md` explains why things are built this way
3. Individual rules in `rules/` are the building codes

## Relationship to CLAUDE.md

`CLAUDE.md` is the Claude-specific front door (MCP tools, CLI commands, trust boundary). `.ai/` contains the **engineering principles** that apply regardless of which AI tool is running. They complement each other: CLAUDE.md says HOW to interact with this specific repo's APIs; `.ai/` says HOW TO THINK about building software here.

## Maintenance

When a rule changes in `~/.claude/rules/`, update the corresponding file in `.ai/rules/`. When a load-bearing decision is made, add it to `DECISIONS.md`. The `providers/` files are generated from the rules — regenerate them when rules change significantly.
