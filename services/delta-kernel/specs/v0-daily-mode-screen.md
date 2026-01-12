# Delta-State Fabric v0 — Daily Mode Screen Behavior

**Status:** LOCKED
**Version:** 0.1.0

---

## Purpose

The Daily Mode Screen is the **command center**.
It shows:
- Current Mode
- Signal buckets (why you're in this mode)
- Prepared actions (filtered by mode)
- Transition conditions (what would change the mode)

No AI decisions at runtime. Pure LUT rendering.

---

## Screen Structure

```
┌─────────────────────────────────────────┐
│  MODE: CLOSE_LOOPS                      │
│  ─────────────────────────────────────  │
│                                         │
│  SIGNALS                                │
│  ├─ sleep_hours:    OK (6.5h)           │
│  ├─ open_loops:     LOW (5 open)        │
│  ├─ assets_shipped: LOW (0)             │
│  ├─ deep_work:      LOW (0 blocks)      │
│  └─ money_delta:    OK (+$200)          │
│                                         │
│  WHY THIS MODE                          │
│  → open_loops is LOW (≥4)               │
│  → Global override triggered            │
│                                         │
│  ALLOWED ACTIONS                        │
│  ├─ [x] Reply to Alex (Thread T1)       │
│  ├─ [ ] Complete: Call Sarah            │
│  ├─ [ ] Complete: Send invoice          │
│  └─ [ ] Review pending messages         │
│                                         │
│  TRANSITION CONDITIONS                  │
│  → To BUILD: Close 3 more loops         │
│  → To RECOVER: Sleep drops below 6h     │
│                                         │
└─────────────────────────────────────────┘
```

---

## Data Model

```typescript
DailyScreenData {
  mode: Mode;
  signals: {
    sleep_hours: { raw: number; bucket: Bucket };
    open_loops: { raw: number; bucket: Bucket };
    assets_shipped: { raw: number; bucket: Bucket };
    deep_work_blocks: { raw: number; bucket: Bucket };
    money_delta: { raw: number; bucket: Bucket };
  };
  mode_reason: string[];
  allowed_actions: PreparedAction[];
  transition_hints: TransitionHint[];
}
```

---

## PreparedAction

Actions are pre-filtered by mode contract.

```typescript
PreparedAction {
  action_id: UUID;
  action_type: 'reply_message' | 'complete_task' | 'review_thread' | 'create_asset' | 'delegate';
  label: string;
  entity_id: UUID;
  priority: Priority;
  is_overdue: boolean;
}
```

Only actions matching `MODE_ALLOWED_ACTIONS[mode]` are shown.

---

## Action Type → Mode Mapping

| Action Type     | Allowed In Modes                    |
|-----------------|-------------------------------------|
| reply_message   | CLOSE_LOOPS                         |
| complete_task   | CLOSE_LOOPS, BUILD                  |
| review_thread   | CLOSE_LOOPS                         |
| create_asset    | BUILD                               |
| extend_asset    | COMPOUND                            |
| delegate        | SCALE                               |
| rest            | RECOVER                             |
| light_admin     | RECOVER                             |

---

## TransitionHint

Shows what would change the mode.

```typescript
TransitionHint {
  target_mode: Mode;
  condition: string;
  distance: string; // "Close 3 loops", "Sleep 1.5h more"
}
```

---

## Rendering Rules

1. **Mode** — Read from SystemState
2. **Signals** — Bucket raw values, show both
3. **Mode Reason** — Explain which rule fired (global override or primary)
4. **Allowed Actions** — Filter by mode contract, sort by priority + overdue
5. **Transition Hints** — Calculate distance to next mode

---

## No AI at Render Time

The screen is built from:
- SystemState entity (mode + signals)
- Inbox entity (queues)
- Task entities (for action list)
- Thread entities (for message actions)
- Routing LUT (for transition hints)

Pure data transforms. No inference.
