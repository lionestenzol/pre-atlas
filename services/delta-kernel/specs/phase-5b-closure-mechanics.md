# Phase 5B — Closure Mechanics Core

**Version:** 1.0
**Date:** 2026-01-09
**Status:** IMPLEMENTED

---

## Overview

Phase 5B establishes closure as a **real state-transition event** with automatic mode flips and streak compounding. This transforms the system from symbolic counters to a sovereign cybernetic constitution.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 5B — CLOSURE MECHANICS                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ close_loop   │───▶│ Atomic Delta │───▶│ Mode Transition      │  │
│  │ API Endpoint │    │ (Leaf Patches)│    │ Engine               │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         │                                          │                 │
│         ▼                                          ▼                 │
│  ┌──────────────┐                        ┌──────────────────────┐   │
│  │ closures.json│                        │ Governance Daemon    │   │
│  │ (Registry)   │                        │ (15-min recalc)      │   │
│  └──────────────┘                        └──────────────────────┘   │
│         │                                          │                 │
│         ▼                                          ▼                 │
│  ┌──────────────┐                        ┌──────────────────────┐   │
│  │ Streak       │                        │ Day Boundary         │   │
│  │ Engine       │                        │ Jobs                 │   │
│  └──────────────┘                        └──────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Law Genesis Layer

**Location:** `services/delta-kernel/src/core/delta.ts:89-104`

The kernel's `applyPatch()` function now auto-creates parent nodes before leaf-patch operations. This enables constitutional state branching without pre-existing structure.

```typescript
function ensurePathExists(obj: Record<string, unknown>, path: string): void {
  const parts = path.split('/').filter(Boolean).slice(0, -1);
  let current: Record<string, unknown> = obj;
  for (const part of parts) {
    if (!current[part] || typeof current[part] !== 'object') {
      current[part] = {};
    }
    current = current[part] as Record<string, unknown>;
  }
}
```

**Behavior:**
- Leaf-patch to `/enforcement/violations_count` auto-creates `/enforcement` if missing
- Enables law branches to be written without initialization
- No more "cannot read property of undefined" errors

---

### 2. Canonical Closure Event

**Endpoint:** `POST /api/law/close_loop`
**Location:** `services/delta-kernel/src/api/server.ts:718-1029`

**Request Body:**
```json
{
  "loop_id": "optional-unique-id",
  "title": "Loop title for display",
  "outcome": "closed" | "archived"
}
```

**Atomic Operations (Single Delta):**

| Path | Operation | Description |
|------|-----------|-------------|
| `/enforcement/violations_count` | → 0 | Reset violations |
| `/enforcement/closure_log` | append | Add closure entry |
| `/metrics/closed_loops_total` | += 1 | Increment counter |
| `/metrics/last_closure_at` | = now | Timestamp |
| `/metrics/closure_ratio` | recompute | closed / (open + closed) |
| `/metrics/open_loops` | refresh | From cognitive_state.json |
| `/metrics/closures_today` | count | Today's closures |
| `/build_allowed` | compute | From mode rules |
| `/mode` | conditional | Flip if ratio crosses threshold |
| `/streak_days` | conditional | +1 if BUILD mode |

**Idempotency:**
- If `loop_id` provided and already closed → returns 409 Conflict
- Prevents double-counting and duplicate entries

**Response:**
```json
{
  "success": true,
  "closure": { "ts": 1234567890, "loop_id": "...", "title": "...", "outcome": "closed" },
  "metrics": {
    "closed_loops_total": 15,
    "closure_ratio": 0.65,
    "open_loops": 8,
    "closures_today": 3
  },
  "mode": "BUILD",
  "mode_changed": true,
  "build_allowed": true,
  "violations_reset": true,
  "streak": {
    "days": 5,
    "updated": true,
    "best": 7,
    "build_only": true
  },
  "physical_closure": "attempted"
}
```

---

### 3. Cognitive Closure Registry

**Location:** `services/cognitive-sensor/closures.json`
**Schema:** `contracts/schemas/Closures.v1.json`

```json
{
  "closures": [
    {
      "ts": 1234567890,
      "loop_id": "uuid-or-null",
      "title": "Loop title",
      "outcome": "closed"
    }
  ],
  "stats": {
    "total_closures": 15,
    "closures_today": 3,
    "last_closure_at": 1234567890,
    "streak_days": 5,
    "last_streak_date": "2026-01-09",
    "best_streak": 7
  }
}
```

**Operations:**
- Append-only `closures[]` array
- Stats recomputed on each closure
- Daily counter resets at `day_start`

---

### 4. Physical Loop Closure

**Location:** `services/delta-kernel/src/api/server.ts:866-898`

When `loop_id` is provided:

1. **Remove from `loops_latest.json`:**
   - Filters out matching `id` or `loop_id`
   - Writes updated array

2. **Append to `loops_closed.json`:**
   - Creates archive record with `closed_at` timestamp
   - Preserves closure history

**Behavior:** Best-effort (logs errors but doesn't fail request)

---

### 5. Mode Transition Rules

**Location:** `services/delta-kernel/src/api/server.ts:826-841`

| closure_ratio | Mode | build_allowed |
|---------------|------|---------------|
| ≥ 0.80 | SCALE | true |
| ≥ 0.60 | BUILD | true |
| ≥ 0.40 | MAINTENANCE | false |
| < 0.40 | CLOSURE | false |

**Formula:**
```
closure_ratio = closed_loops_total / (open_loops + closed_loops_total)
```

**Transition Logging:**
```
/last_mode_transition_at → timestamp
/last_mode_transition_reason → "Closure event: ratio=0.65"
```

---

### 6. Streak Compounding Engine

**Location:** `services/delta-kernel/src/api/server.ts:843-856`

**Rules:**
1. Streak increments ONLY if:
   - This is the first closure of the day (`last_streak_date !== today`)
   - Resulting mode is BUILD or SCALE
2. `best_streak` updated if current exceeds it
3. Streak resets to 0 at `day_end` if no productive closure occurred

**BUILD-Only Enforcement:**
```typescript
if (isFirstClosureToday && (newMode === 'BUILD' || newMode === 'SCALE')) {
  closuresRegistry.stats.streak_days += 1;
}
```

---

### 7. Autonomous Mode Recalculation

**Location:** `services/delta-kernel/src/governance/governance_daemon.ts:377-478`

**Schedule:**
- Every 15 minutes (`MODE_RECALC_CRON = '*/15 * * * *'`)
- At `day_start` (06:00)
- At `day_end` (22:00)

**Process:**
1. Read `cognitive_state.json` → `open_loops`
2. Read `closures.json` → `total_closures`
3. Compute `closure_ratio`
4. Apply mode rules
5. Patch system_state if mode changed

**Delta Author:** `governance_daemon`

---

### 8. Day Boundary Jobs

**Day Start (06:00):**
- Reset `closures_today` to 0
- Run mode recalculation
- Log `day.mode_at_start`

**Day End (22:00):**
- Check if productive BUILD closure occurred
- If `last_streak_date !== today` → reset `streak_days` to 0
- Run mode recalculation
- Log `day.closures_count`, `day.streak_reset`, `day.mode_at_end`

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/law/close_loop` | POST | Canonical closure event |
| `/api/law/acknowledge` | POST | Acknowledge daily order |
| `/api/law/archive` | POST | Archive a loop |
| `/api/law/violation` | POST | Log build violation |
| `/api/law/override` | POST | Log enforcement override |
| `/api/law/refresh` | POST | Request system refresh |
| `/api/daemon/status` | GET | Daemon state + job history |
| `/api/daemon/run` | POST | Manually trigger a job |
| `/api/state/unified` | GET | Merged Delta + Cognitive state |
| `/api/state/unified/stream` | GET (SSE) | Realtime unified_state + delta_created events |

---

## Contract Schema

**File:** `contracts/schemas/Closures.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "Closures.v1",
  "title": "Closure Registry",
  "type": "object",
  "required": ["closures", "stats"],
  "properties": {
    "closures": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ts", "outcome"],
        "properties": {
          "ts": { "type": "integer" },
          "loop_id": { "type": ["string", "null"] },
          "title": { "type": ["string", "null"] },
          "outcome": { "enum": ["closed", "archived"] }
        }
      }
    },
    "stats": {
      "type": "object",
      "required": ["total_closures", "closures_today", "streak_days", "best_streak"],
      "properties": {
        "total_closures": { "type": "integer", "minimum": 0 },
        "closures_today": { "type": "integer", "minimum": 0 },
        "last_closure_at": { "type": ["integer", "null"] },
        "streak_days": { "type": "integer", "minimum": 0 },
        "last_streak_date": { "type": ["string", "null"], "format": "date" },
        "best_streak": { "type": "integer", "minimum": 0 }
      }
    }
  }
}
```

**Validation:** `services/cognitive-sensor/validate.py:validate_closures()`

---

## Files Modified

| File | Changes |
|------|---------|
| `delta.ts` | Added `ensurePathExists()` (Law Genesis Layer) |
| `server.ts` | Rewrote `/api/law/close_loop` with atomic leaf-patches |
| `governance_daemon.ts` | Added `mode_recalc` job, streak reset in `day_end` |
| `validate.py` | Added `validate_closures()` function |
| `Closures.v1.json` | New schema file |

---

## Smoke Tests

1. **Law Genesis:** Call close_loop with no prior enforcement node → must succeed
2. **BUILD Streak:** Close during BUILD → streak increments by 1
3. **Non-BUILD Streak:** Close during MAINTENANCE/CLOSURE → streak unchanged
4. **Idempotency:** Repeat same loop_id → returns 409, no duplicate counters
5. **Mode Flip:** Close enough loops to cross ratio threshold → mode changes
6. **Day-End Reset:** No closures today → streak resets to 0

---

## Design Principles

1. **Atomic Operations:** All state changes in a single delta
2. **Leaf-Patch Only:** No subtree replacements that clobber sibling fields
3. **Idempotent Closures:** Same input produces same output
4. **BUILD-Only Streaks:** No inflation from non-productive days
5. **Autonomous Governance:** Mode self-corrects without manual intervention
6. **Contract Enforcement:** All writes validated against JSON Schema

---

*Phase 5B is now a sovereign cybernetic constitution.*
