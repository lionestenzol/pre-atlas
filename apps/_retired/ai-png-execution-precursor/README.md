# AI-PNG Execution (precursor)

Extracted from conversation #360 "Decimal vs Binary Logic" (2025-02-24), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/360_decimal-vs-binary-logic/`), verdict MINE, decided 2026-04-21.

## What this is

A minimal, working port of the thread's core idea: encode a function's source code as base64 inside a PNG's own metadata, so the image file carries executable logic alongside its pixels. `ai_png_execution.py` is the whole thing — `store_execution_in_png()` writes it, `retrieve_execution_from_png()` reads it back.

Bug fixed during porting: the original transcript's write path used metadata key `"execution_logic"` while its read path looked for `"execution_storage"` — a mismatch that meant the original code never actually round-tripped, despite reading as complete in the conversation. Both sides use `"execution_logic"` here. Round-trip is covered by `test_ai_png_execution.py` (2/2 passing).

## What this is not

The source thread also speculated at length about "AI-PNG execution replacing installed applications" (messaging apps, video players, browsers) — that's aspirational framing from the conversation, not working code, and isn't ported here. This module is scoped to the one concrete, testable idea: PNG-as-metadata-carrier.

## Relationship to the existing PNG-Substrate work

This predates and is unrelated to the later PNG-Substrate / ST3GG steganography work (Claude's memory: `project_png_substrate_seed.md`, `project_st3gg_png_substrate_pairing.md`) — that project embeds data in pixel content via steganography; this stores it in PNG text metadata (`tEXt` chunks), a much simpler and more fragile mechanism (metadata is stripped by most image processing, unlike pixel-level steganography). Kept as a separate, small artifact rather than merged into that project.

## Run the tests

```
python -m pytest test_ai_png_execution.py -v
```
