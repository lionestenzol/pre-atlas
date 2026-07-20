# Code Module Memory Store

Extracted from conversation #557 "Phase 3 AI System" (2025-02-02), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/557_phase-3-ai-system/`), verdict MINE, decided 2026-04-21.

## What this is

The source thread built a multi-agent PHP pipeline (planner, code generator, refinement, memory, testing agents) that its own diagnostic script confirmed was fully working by the end of the conversation. The individual agents' full source was never captured in the harvest (355 code blocks, but 190 `unspecified` + 87 `cmd` — mostly interactive dotenv/Composer error-fixing, not agent logic). What *is* fully specified, and referenced dozens of times across the thread, is the data structure the "memory agent" used: a `memory.json` file storing named code modules as `{"modules": {name: {"code": <base64>}}}`. `module_memory.py` ports that store — `save_module`/`load_module`/`list_modules` — since it's the one concrete piece of the pipeline this thread actually nailed down. 5/5 tests passing.

## What was left out

The planner/code-generator/refinement/testing agents themselves, the OpenAI completions call wiring, and the `.env`/Composer dependency debugging that makes up most of the thread — none of that had complete, coherent source in the harvest to port.

## Run the tests

```
python -m pytest test_module_memory.py -v
```
