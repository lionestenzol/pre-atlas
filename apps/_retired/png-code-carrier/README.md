# PNG Code Carrier

Extracted from conversation #361 "Chatbot Preload Optimization" (2025-02-23), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/361_chatbot-preload-optimization/`), verdict MINE, decided 2026-04-21.

## What this is

Under an "AI-PNG execution / self-improving digital DNA" narrative, the source thread's first code block contains a real, legitimate technique: embed a Base64-encoded script in a PNG's `tEXt` metadata chunk via Pillow's `PngInfo`, so the file is a viewable image and a portable code container at once (the same mechanism Stable Diffusion uses to embed generation parameters in its output PNGs — not novel, but real). `png_code_carrier.py` ports `embed_script`/`extract_script`, verified round-trip: 5/5 tests passing.

## What was changed from the source

The source's `extract_and_run()` called `exec()` on whatever decoded from the PNG unconditionally — no gate at all, arbitrary code execution from a file that could come from anywhere. Ported as two separate functions instead: `extract_script()` only reads and decodes (no execution), and `run_extracted_script()` requires an explicit `allow_exec=True` and raises `PermissionError` otherwise — a file's metadata isn't a trust boundary, so nothing here executes by default.

## What was left out

Everything past the first working prototype block was "AI-Symbolic/AI-PNG execution" narrative (self-optimizing intelligence fields, P2P execution networks, wave-based transmission) with no corresponding code — 181 of the thread's 278 code blocks were `unspecified`-language narrative filler, not real logic.

## Run the tests

```
python -m pytest test_png_code_carrier.py -v
```
