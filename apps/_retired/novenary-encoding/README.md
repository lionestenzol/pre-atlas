# Novenary (base-9) Encoding

Extracted from conversation #266 "ChatGPT o1 Overview" (2025-02-27), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/266_chatgpt-o1-overview/`), verdict MINE, decided 2026-04-21.

## What this is

The source thread's code blocks were an "AI self ping-pong" prompt-chaining demo requiring a live OpenAI key — not testable offline, and not what the triage note ("92 Python blocks on Novenary base-9 encoding") was actually pointing at. The real content is a formal math spec in the thread's final assistant message, which this module implements and tests:

- **Ternary-pair packing**: two base-3 digits pack into one base-9 digit as `d = t_low + 3*t_high`; unpacked via `t_low = d % 3, t_high = d // 3`. (`ternary_pair_to_digit` / `digit_to_ternary_pair`, plus sequence-level `trits_to_novenary` / `novenary_to_trits`.)
- **Standard base-9 positional notation** for integers (`int_to_base9` / `base9_to_int`).

18/18 tests passing, covering round-trips both directions and known values.

## What was left out

The spec's "multi-layer language" framing (split data into N layers, each its own novenary sequence, layers feed into each other DNA-like) names an idea without a concrete algorithm — no rule for what determines a layer boundary or what "feeding into" means computationally. There's nothing testable to port for that part; it's noted here rather than faked with an arbitrary implementation.

## Run the tests

```
python -m pytest test_novenary.py -v
```
