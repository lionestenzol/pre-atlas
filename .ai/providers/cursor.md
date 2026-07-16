# Cursor Integration Guide

How to load this project's engineering rules into Cursor IDE.

## Option 1: Project Rules (Recommended)

Cursor reads `.cursor/rules` files from your project root.

1. Create `.cursor/rules/engineering.mdc`:

```markdown
---
description: Pre Atlas engineering rules
globs: **/*
alwaysApply: true
---

[paste ENGINEERING_HANDBOOK.md content here]
```

2. For language-specific rules, create additional rule files:

`.cursor/rules/python.mdc`:
```markdown
---
description: Python coding conventions
globs: "**/*.py"
---

[paste .ai/lang/python.md content here]
```

`.cursor/rules/typescript.mdc`:
```markdown
---
description: TypeScript coding conventions
globs: "**/*.{ts,tsx,js,jsx}"
---

[paste .ai/lang/typescript.md content here]
```

`.cursor/rules/wasp.mdc`:
```markdown
---
description: Wasp framework conventions
globs: "**/*.wasp,schema.prisma,src/**/*"
---

[paste .ai/lang/wasp.md content here]
```

## Option 2: .cursorrules (Legacy)

Create `.cursorrules` at project root with the handbook content. This is the older format but still supported.

## Option 3: User Rules (Global)

For rules that apply across all projects:

1. Cursor Settings > General > Rules for AI
2. Paste the minimal system prompt (from the ChatGPT provider guide)

## Cursor-Specific Advantages

Cursor has direct file system access, so it can:
- Read source files for context (like Claude Code)
- Apply code changes inline
- Run terminal commands

This means the rules about "verify before verdict" and "assemble first" can be followed more faithfully than in pure-chat providers.

## What Cursor Won't Have

- No MCP tool integration (unless configured separately)
- No persistent memory system (use DECISIONS.md)
- No custom agent orchestration
- No background task spawning

## File Placement

```
project-root/
  .cursor/
    rules/
      engineering.mdc    # Full handbook
      python.mdc         # Python rules (*.py files)
      typescript.mdc     # TypeScript rules (*.ts/*.tsx files)
      wasp.mdc           # Wasp rules (*.wasp + schema + src/)
  .ai/                   # This directory (source of truth)
  DECISIONS.md           # Architectural decisions
```

Keep `.ai/` as the source of truth. When rules change, update `.ai/` first, then sync to `.cursor/rules/`.
