# Gemini Integration Guide

How to load this project's engineering rules into Google Gemini (AI Studio, API, or Gemini Advanced).

## Option 1: Google AI Studio (System Instructions)

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Create a new prompt
3. In **System Instructions**, paste the contents of `../ENGINEERING_HANDBOOK.md`
4. Upload files to the context:
   - `../../DECISIONS.md` (architectural decisions)
   - Relevant language files from `../lang/`
5. Save as a reusable prompt

## Option 2: Gemini API

```python
import google.generativeai as genai

genai.configure(api_key="your-key")

with open(".ai/ENGINEERING_HANDBOOK.md") as f:
    handbook = f.read()

model = genai.GenerativeModel(
    model_name="gemini-2.5-pro",
    system_instruction=f"You are an engineering assistant. Follow these rules:\n\n{handbook}"
)

response = model.generate_content("Your task here...")
```

## Option 3: Gemini Advanced (Google One AI Premium)

1. Start a conversation in Gemini Advanced
2. In your first message, paste:

```
Before we begin, here are the engineering rules for this project. Follow them in all responses:

[paste ENGINEERING_HANDBOOK.md content]
```

3. Upload `DECISIONS.md` as a file attachment for architectural context

## Option 4: Gems (Custom Gemini Bots)

1. Go to Gemini > Gems > Create
2. Paste the minimal system prompt (from chatgpt.md Option 1) as the Gem's instructions
3. Upload `ENGINEERING_HANDBOOK.md` and `DECISIONS.md` as knowledge

## Token Budget

Gemini 2.5 Pro has a 1M+ token context window. All project files fit comfortably:

| File | Approx. Tokens |
|------|----------------|
| ENGINEERING_HANDBOOK.md | ~3,500 |
| DECISIONS.md | ~5,000 |
| All language files combined | ~3,000 |

Total: ~11,500 tokens. Less than 2% of Gemini's context window.

## What Gemini Won't Have

- No persistent file system access across sessions
- No MCP tool integration
- No git operations
- No code execution in your local environment

Mitigate by: uploading relevant source files, using Gemini's code execution sandbox for analysis, and manually running suggested commands.
