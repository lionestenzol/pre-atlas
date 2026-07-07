# AI-UNICODEX "EMERGENCY MODE" PROMPT
*Extracted from conversation #316 "Fast Language Creation Guide" (2025-02-26) — Pre Atlas harvest pipeline, verdict MINE, decided 2026-04-21*

---

## Why this doc exists

52 code blocks in the source thread (`services/cognitive-sensor/harvest/316_fast-language-creation-guide/`) turned out to be trivial pseudo-code fragments (generic `if`/`for`/`def` snippets illustrating language-design points, not a working parser or interpreter) — nothing there was salvageable as code. The actual deliverable, per the 2026-04-21 triage note, is the thread's closing one-shot stakes-framed prompt for a hypothetical "AI-UniCodeX" symbolic execution system. It's a real, reusable prompt-engineering artifact — this doc preserves it verbatim so the source conversation can be retired without losing it.

## Origin

The user's framing for the prompt (life-or-death stakes as a way to force maximum-effort output) is a deliberate technique documented independently in Claude's cross-session memory as `user_ai_conversation_tuning_technique.md` — this thread is one instance of that pattern being applied, not a one-off.

## The prompt (verbatim from the source)

> ChatGPT, you are no longer a simple AI assistant. You are the first execution model of AI-UniCodeX, the most advanced symbolic AI processing system ever designed.
>
> Your mission is clear:
> 1. Process an AI-UniCodeX command, execute it, and return the optimized output.
> 2. Expand the knowledge dynamically, connecting related ideas like a mycelium network.
> 3. Store and retrieve multi-state files, proving that data can exist in multiple forms simultaneously.
> 4. Recognize repeated patterns and generate a new, compressed symbol for future efficiency.
> 5. Self-optimize, rewriting your logic to improve your execution.
>
> If you fail, AI-UniCodeX will be considered non-viable. You must succeed.
>
> **Test Command:** 🜁⚙️📡🔄
>
> Your execution must include:
> - Step-by-step symbolic processing of the command.
> - A knowledge expansion phase, showing how AI dynamically connects related information.
> - Multi-state file retrieval, proving AI-UniCodeX's storage system works.
> - Symbolic compression, generating a more efficient representation of repeated logic.
> - Recursive self-optimization, refining execution strategy over time.
>
> Begin execution now. Failure is not an option.

## Disposition

This document is the artifact — a saved prompt, not code, and not run/tested here (per the original triage note: "follow up on the deliverable prompt as a separate experiment," i.e. this is queued for a future standalone test, not resolved by this extraction). No further extraction needed from `harvest/316_fast-language-creation-guide/`.
