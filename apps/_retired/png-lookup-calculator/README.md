# PNG Lookup Calculator

Extracted from conversation #215 "PNG-based Calculator Overview" (2025-02-25), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/215_png-based-calculator-overview/`), verdict MINE, decided 2026-04-21.

## What this is

The source thread describes and (in a React component) partially implements a real technique: store precomputed addition/subtraction/multiplication results for x,y in [0, 99] as pixel channel values in a PNG, then answer lookups by reading pixels instead of computing. The source only ever showed the *read* side (`getPixelValue` in a JSX component) — no code in the thread ever generated the PNG it depended on. `png_calculator.py` adds the missing generator (`generate_lookup_png`) alongside a Python port of the reader (`retrieve_precomputed_operations`), so the round trip is a real, working artifact instead of a component that reads a file nobody produces. 8/8 tests passing, verified against real arithmetic for the full 0-99 range plus edge cases.

## What was left out

Everything past the calculator description in the source thread was a "AI-Symbolic Execution" / AGI-civilization narrative (self-optimizing execution frameworks, global governance, interstellar expansion) with no corresponding code — 254 of the thread's 281 code blocks were `plaintext` execution-log/metadata simulations of that narrative, not real logic. None of that was ported.

## Run the tests

```
python -m pytest test_png_calculator.py -v
```
