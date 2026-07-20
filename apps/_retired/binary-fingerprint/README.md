# Binary Fingerprint + Execution Cache

Extracted from conversation #81 "Universal Programming Table Setup" (2025-03-07), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/81_universal-programming-table-setup/`), verdict MINE, decided 2026-04-21.

## What this is

The largest single harvested thread (931 messages, 519 code blocks) circles an ever-more-elaborate "AI code database mapping Python <-> C++ <-> Assembly <-> Binary" that never converges on one working implementation (228 hedge signals — the highest of any harvested thread). Two pieces recur identically across the fragments and are fully self-contained:

1. `calculate_entropy` (blocks ~360-386) — a real, correct Shannon entropy function over a byte string, used to fingerprint compiled binaries alongside a SHA256 hash.
2. an execution cache — the thread's own last message describes it directly: *"if code was previously executed, results are retrieved instantly"* instead of re-running. Described in prose, never actually coded anywhere in the harvest.

`fingerprint.py` ports both: `calculate_entropy`/`fingerprint_bytes` verbatim-equivalent to the source's entropy function, and `ExecutionCache`, which the source never wrote — implemented here keyed on source-code hash (rather than compiled-binary hash) since that's the case actually exercisable without a C++ toolchain. 8/8 tests passing.

## What was left out

The C++ compilation pipeline (`g++ -S`, binary disassembly, `magic`-based file typing) depends on a toolchain not present in this repo and was never shown as one coherent script in the harvest — only scattered fragments repeating the same few lines. The "Universal Programming Table" SQL/JSON schema itself was proposed multiple times with different column sets each time and never settled, so no single schema was authoritative enough to port.

## Run the tests

```
python -m pytest test_fingerprint.py -v
```
