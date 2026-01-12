# Delta-State Fabric v0 — Routing Table

**Status:** LOCKED
**Version:** 0.1.0

There is exactly **one active Mode** at all times:

```
RECOVER
CLOSE_LOOPS
BUILD
COMPOUND
SCALE
```

Routing is **deterministic** — no probabilities.

---

## Signal Buckets

Raw signals are bucketed into LOW / OK / HIGH.

| Signal           | LOW | OK           | HIGH    |
| ---------------- | --- | ------------ | ------- |
| sleep_hours      | <6  | 6–7.5        | ≥7.5    |
| open_loops       | ≥4  | 2–3          | ≤1      |
| assets_shipped   | 0   | 1            | ≥2      |
| deep_work_blocks | 0   | 1            | ≥2      |
| money_delta      | ≤0  | >0 & <target | ≥target |

---

## Global Override Rules (highest priority)

These apply **from any state**.

| Condition         | Next Mode   |
| ----------------- | ----------- |
| sleep_hours = LOW | RECOVER     |
| open_loops = HIGH | CLOSE_LOOPS |

Note: `open_loops = HIGH` means ≤1 open loops (good state).
The override triggers on `open_loops = LOW` (≥4 loops = bad).

---

## Primary Routing Table

| Current Mode | Condition                                                  | Next Mode   |
| ------------ | ---------------------------------------------------------- | ----------- |
| RECOVER      | sleep_hours = OK or HIGH                                   | CLOSE_LOOPS |
| CLOSE_LOOPS  | open_loops = OK or HIGH                                    | BUILD       |
| BUILD        | assets_shipped = OK or HIGH                                | COMPOUND    |
| COMPOUND     | deep_work_blocks = OK or HIGH AND money_delta = OK or HIGH | SCALE       |
| SCALE        | assets_shipped = LOW                                       | BUILD       |
| SCALE        | money_delta = LOW                                          | CLOSE_LOOPS |

If no rule fires → remain in current Mode.

---

## Behavioral Contract per Mode

| Mode        | System Is Allowed To Prepare                   |
| ----------- | ---------------------------------------------- |
| RECOVER     | Rest tasks, health actions, sleep, light admin |
| CLOSE_LOOPS | Finish tasks, reply messages, clean queues     |
| BUILD       | Draft new assets, plans, systems               |
| COMPOUND    | Extend existing assets, marketing, leverage    |
| SCALE       | Hiring, delegation, infrastructure, funding    |

---

## Runtime Law

At runtime:

```
(current_mode, bucketed_signals) → next_mode
```

is resolved by table lookup only.

- No AI
- No heuristics
- No drift
