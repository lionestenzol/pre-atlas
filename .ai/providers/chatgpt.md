# ChatGPT Integration Guide

How to load this project's engineering rules into ChatGPT (Custom GPT or API).

## Option 1: Custom GPT (ChatGPT Plus / Team / Enterprise)

1. Go to [chat.openai.com](https://chat.openai.com) > Explore GPTs > Create
2. In the **Instructions** field, paste the contents of `../ENGINEERING_HANDBOOK.md`
3. In **Knowledge**, upload these files:
   - `../ENGINEERING_HANDBOOK.md` (core rules)
   - `../../DECISIONS.md` (architectural decisions)
   - `../../CLAUDE.md` (project context -- rename to `PROJECT_CONTEXT.md` if you prefer)
   - Relevant language files from `../lang/` for the current task
4. Set the GPT name (e.g., "Pre Atlas Engineer")
5. Save as private GPT

### What to paste as system instructions

The `ENGINEERING_HANDBOOK.md` is designed to work directly as a ChatGPT system prompt. It covers all 11 rules plus language-specific appendices.

For shorter context windows, use this minimal system prompt:

```
You are an engineering assistant for the Pre Atlas project. Follow these rules:
1. Assemble first -- use existing libraries for solved categories before hand-rolling
2. Code = furniture -- fix bugs inline, never just document them
3. Verify before verdict -- research claims about tools/libraries before asserting
4. No building without a locked plan -- WHAT + WHY before code
5. Immutability -- never mutate objects, always create new copies
6. TDD -- write tests first, 80% minimum coverage
7. Security -- never hardcode secrets, validate all inputs, parameterize queries
8. Ship small -- smallest real output first, iterate fast

See the Knowledge files for full details.
```

## Option 2: API (Responses API or Chat Completions)

```python
import openai

client = openai.OpenAI()

with open(".ai/ENGINEERING_HANDBOOK.md") as f:
    handbook = f.read()

with open("DECISIONS.md") as f:
    decisions = f.read()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": f"You are an engineering assistant. Follow these rules:\n\n{handbook}\n\nArchitectural decisions:\n\n{decisions}"
        },
        {
            "role": "user",
            "content": "Your task here..."
        }
    ]
)
```

## Option 3: ChatGPT Projects (ChatGPT Plus)

1. Create a new Project in ChatGPT
2. In Project Instructions, paste the minimal system prompt above
3. Upload `ENGINEERING_HANDBOOK.md` and `DECISIONS.md` as project files
4. All conversations within the project inherit the rules

## Token Budget

| File | Approx. Tokens |
|------|----------------|
| ENGINEERING_HANDBOOK.md | ~3,500 |
| DECISIONS.md | ~5,000 |
| Per language file | ~500-1,500 |
| CLAUDE.md (project context) | ~2,000 |

Total with all files: ~12,000 tokens of system context. Well within GPT-4o's 128k window.

## What ChatGPT Won't Have

- No persistent memory across sessions (use DECISIONS.md as the substitute)
- No file system access (can't run code-recon, grep, or file searches)
- No MCP tool integration
- No git operations

Mitigate by: pasting relevant file contents into the conversation, using the Code Interpreter for analysis, and manually running commands ChatGPT suggests.
