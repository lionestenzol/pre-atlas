# Phase 6A — Work Admission Control

**Version:** 1.0
**Date:** 2026-01-09
**Status:** SPECIFICATION

---

## Overview

Phase 6A transforms Pre-Atlas from a human governance system into a **universal work controller**. All work — human and machine — passes through a single admission gate before execution.

This is not orchestration. This is **law applied to machines**.

---

## Core Primitives

### 1. Work Request
### 2. Work Complete
### 3. Bounded Job Queue

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 6A — WORK ADMISSION CONTROL                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐                                               │
│  │ /api/work/request│◄────── AI Agent / Human / Process             │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                    ADMISSION GATE                         │       │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐            │       │
│  │  │ Mode Check │ │ Capacity   │ │ Dependency │            │       │
│  │  │ (build_    │ │ Check      │ │ Check      │            │       │
│  │  │  allowed)  │ │ (slots)    │ │ (blocked?) │            │       │
│  │  └────────────┘ └────────────┘ └────────────┘            │       │
│  └──────────────────────────────────────────────────────────┘       │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────┐     ┌──────────────────┐                      │
│  │ APPROVED         │     │ QUEUED           │                      │
│  │ (start now)      │     │ (wait in queue)  │                      │
│  └────────┬─────────┘     └────────┬─────────┘                      │
│           │                        │                                 │
│           ▼                        ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                    WORK LEDGER                            │       │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐            │       │
│  │  │ Active     │ │ Queued     │ │ Completed  │            │       │
│  │  │ Jobs       │ │ Jobs       │ │ Jobs       │            │       │
│  │  └────────────┘ └────────────┘ └────────────┘            │       │
│  └──────────────────────────────────────────────────────────┘       │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │/api/work/complete│◄────── Agent reports done                     │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                    CLOSURE ENGINE                         │       │
│  │  • Update closures.json                                   │       │
│  │  • Free capacity slot                                     │       │
│  │  • Unlock dependents                                      │       │
│  │  • Advance queue                                          │       │
│  │  • Update streaks                                         │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Endpoint 1: POST /api/work/request

**Purpose:** Request permission to start a job.

### Request Body

```json
{
  "job_id": "string (optional, auto-generated if omitted)",
  "type": "string (required: 'human' | 'ai' | 'system')",
  "title": "string (required: human-readable job name)",
  "weight": "number (optional: 1-10, default 1)",
  "agent": "string (optional: 'claude' | 'openai' | 'human' | 'daemon')",
  "depends_on": ["job_id array (optional)"],
  "timeout_ms": "number (optional: max execution time)",
  "metadata": "object (optional: arbitrary context)"
}
```

### Admission Logic

```
1. IF mode === 'CLOSURE' AND type !== 'closure_work':
     RETURN DENIED (reason: "Must close loops first")

2. IF active_jobs >= max_concurrent_jobs:
     IF queue_depth >= max_queue_depth:
       RETURN DENIED (reason: "System at capacity")
     ELSE:
       RETURN QUEUED (position: queue_position)

3. IF depends_on contains incomplete jobs:
     RETURN QUEUED (reason: "Waiting on dependencies", blocked_by: [...])

4. ELSE:
     Add to active_jobs
     RETURN APPROVED (job_id, started_at)
```

### Response: APPROVED

```json
{
  "status": "APPROVED",
  "job_id": "j_abc123",
  "started_at": 1736400000000,
  "expires_at": 1736403600000,
  "slot": 2,
  "total_slots": 3
}
```

### Response: QUEUED

```json
{
  "status": "QUEUED",
  "job_id": "j_abc123",
  "position": 4,
  "queue_depth": 7,
  "reason": "At capacity",
  "blocked_by": [],
  "estimated_wait_ms": 300000
}
```

### Response: DENIED

```json
{
  "status": "DENIED",
  "reason": "Must close loops first",
  "required_action": "Close or archive open loop",
  "mode": "CLOSURE",
  "open_loops": 14,
  "closure_ratio": 6.67
}
```

---

## Endpoint 2: POST /api/work/complete

**Purpose:** Report job completion.

### Request Body

```json
{
  "job_id": "string (required)",
  "outcome": "string (required: 'completed' | 'failed' | 'abandoned')",
  "result": "object (optional: job output)",
  "error": "string (optional: failure reason)",
  "metrics": {
    "duration_ms": "number",
    "tokens_used": "number (for AI jobs)",
    "cost_usd": "number (for AI jobs)"
  }
}
```

### Completion Logic

```
1. Find job in active_jobs or queue
2. IF not found: RETURN 404

3. Record completion in work_ledger:
   - job_id, outcome, completed_at, duration, metrics

4. IF outcome === 'completed':
   - Increment closure count
   - Update streak (if BUILD mode)
   - Add to closures.json

5. Free capacity slot

6. Check queue for next eligible job:
   - Must pass admission checks
   - Dependencies must be met
   - Promote to active if eligible

7. Notify any waiting dependents

8. RETURN completion receipt
```

### Response

```json
{
  "success": true,
  "job_id": "j_abc123",
  "outcome": "completed",
  "completed_at": 1736401000000,
  "duration_ms": 45000,
  "freed_slot": 2,
  "queue_advanced": true,
  "next_job_started": "j_def456",
  "closure_count": 16,
  "streak_days": 2
}
```

---

## Endpoint 3: GET /api/work/status

**Purpose:** Query current work state.

### Response

```json
{
  "capacity": {
    "max_concurrent": 3,
    "active": 2,
    "available": 1,
    "queue_depth": 4,
    "max_queue": 20
  },
  "active_jobs": [
    {
      "job_id": "j_abc123",
      "type": "ai",
      "title": "Generate report",
      "agent": "claude",
      "started_at": 1736400000000,
      "elapsed_ms": 30000,
      "timeout_ms": 120000
    }
  ],
  "queued_jobs": [
    {
      "job_id": "j_def456",
      "position": 1,
      "blocked_by": [],
      "queued_at": 1736400500000
    }
  ],
  "mode": "BUILD",
  "build_allowed": true,
  "closure_ratio": 65.0
}
```

---

## Endpoint 4: POST /api/work/cancel

**Purpose:** Cancel a queued or active job.

### Request Body

```json
{
  "job_id": "string (required)",
  "reason": "string (optional)"
}
```

### Response

```json
{
  "success": true,
  "job_id": "j_abc123",
  "was_active": true,
  "freed_slot": true,
  "queue_advanced": true
}
```

---

## Work Ledger Schema

**Location:** `services/cognitive-sensor/work_ledger.json`

```json
{
  "active": [
    {
      "job_id": "j_abc123",
      "type": "ai",
      "title": "Generate quarterly report",
      "agent": "claude",
      "weight": 3,
      "started_at": 1736400000000,
      "timeout_at": 1736403600000,
      "depends_on": [],
      "metadata": {}
    }
  ],
  "queued": [
    {
      "job_id": "j_def456",
      "type": "human",
      "title": "Review generated report",
      "weight": 1,
      "queued_at": 1736400500000,
      "depends_on": ["j_abc123"],
      "position": 1
    }
  ],
  "completed": [
    {
      "job_id": "j_xyz789",
      "type": "ai",
      "title": "Data extraction",
      "outcome": "completed",
      "started_at": 1736390000000,
      "completed_at": 1736391000000,
      "duration_ms": 60000,
      "metrics": {
        "tokens_used": 4500,
        "cost_usd": 0.045
      }
    }
  ],
  "stats": {
    "total_completed": 47,
    "total_failed": 3,
    "total_abandoned": 2,
    "avg_duration_ms": 45000,
    "total_cost_usd": 12.50
  }
}
```

---

## Contract Schema

**File:** `contracts/schemas/WorkLedger.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "WorkLedger.v1",
  "title": "Work Ledger",
  "description": "Universal work admission and completion registry",
  "type": "object",
  "required": ["active", "queued", "completed", "stats"],
  "properties": {
    "active": {
      "type": "array",
      "items": { "$ref": "#/definitions/ActiveJob" }
    },
    "queued": {
      "type": "array",
      "items": { "$ref": "#/definitions/QueuedJob" }
    },
    "completed": {
      "type": "array",
      "items": { "$ref": "#/definitions/CompletedJob" }
    },
    "stats": {
      "type": "object",
      "properties": {
        "total_completed": { "type": "integer", "minimum": 0 },
        "total_failed": { "type": "integer", "minimum": 0 },
        "total_abandoned": { "type": "integer", "minimum": 0 },
        "avg_duration_ms": { "type": "number" },
        "total_cost_usd": { "type": "number" }
      }
    }
  },
  "definitions": {
    "ActiveJob": {
      "type": "object",
      "required": ["job_id", "type", "title", "started_at"],
      "properties": {
        "job_id": { "type": "string" },
        "type": { "enum": ["human", "ai", "system"] },
        "title": { "type": "string" },
        "agent": { "type": "string" },
        "weight": { "type": "integer", "minimum": 1, "maximum": 10 },
        "started_at": { "type": "integer" },
        "timeout_at": { "type": ["integer", "null"] },
        "depends_on": { "type": "array", "items": { "type": "string" } },
        "metadata": { "type": "object" }
      }
    },
    "QueuedJob": {
      "type": "object",
      "required": ["job_id", "type", "title", "queued_at", "position"],
      "properties": {
        "job_id": { "type": "string" },
        "type": { "enum": ["human", "ai", "system"] },
        "title": { "type": "string" },
        "weight": { "type": "integer" },
        "queued_at": { "type": "integer" },
        "depends_on": { "type": "array", "items": { "type": "string" } },
        "position": { "type": "integer", "minimum": 1 }
      }
    },
    "CompletedJob": {
      "type": "object",
      "required": ["job_id", "type", "title", "outcome", "started_at", "completed_at"],
      "properties": {
        "job_id": { "type": "string" },
        "type": { "enum": ["human", "ai", "system"] },
        "title": { "type": "string" },
        "outcome": { "enum": ["completed", "failed", "abandoned"] },
        "started_at": { "type": "integer" },
        "completed_at": { "type": "integer" },
        "duration_ms": { "type": "integer" },
        "error": { "type": ["string", "null"] },
        "metrics": {
          "type": "object",
          "properties": {
            "tokens_used": { "type": "integer" },
            "cost_usd": { "type": "number" }
          }
        }
      }
    }
  }
}
```

---

## Configuration

**Location:** System state or config file

```json
{
  "work_controller": {
    "max_concurrent_jobs": 3,
    "max_queue_depth": 20,
    "default_timeout_ms": 600000,
    "allow_ai_in_closure_mode": false,
    "weight_affects_slots": true,
    "priority_ordering": "fifo"
  }
}
```

### Configuration Rules

| Setting | Default | Description |
|---------|---------|-------------|
| `max_concurrent_jobs` | 3 | Max simultaneous active jobs |
| `max_queue_depth` | 20 | Max queued jobs before denial |
| `default_timeout_ms` | 600000 | 10 minute default timeout |
| `allow_ai_in_closure_mode` | false | Can AI jobs run in CLOSURE mode? |
| `weight_affects_slots` | true | Heavy jobs consume multiple slots |
| `priority_ordering` | "fifo" | Queue order: fifo, priority, weight |

---

## Integration with Existing System

### Mode Enforcement

```typescript
// In admission gate
if (systemState.mode === 'CLOSURE') {
  if (job.type === 'ai' && !config.allow_ai_in_closure_mode) {
    return { status: 'DENIED', reason: 'AI work blocked in CLOSURE mode' };
  }
}

if (!systemState.build_allowed && job.type !== 'closure_work') {
  return { status: 'DENIED', reason: 'Must close loops first' };
}
```

### Closure Unification

When a job completes successfully:

```typescript
// Append to closures.json (same as human closures)
closuresRegistry.closures.push({
  ts: now(),
  loop_id: job.job_id,
  title: job.title,
  outcome: 'closed',
  source: job.type  // 'human' | 'ai' | 'system'
});

closuresRegistry.stats.total_closures++;
closuresRegistry.stats.closures_today++;

// Streak logic (same as Phase 5B)
if (isFirstClosureToday && isBuildMode) {
  closuresRegistry.stats.streak_days++;
}
```

### Daemon Integration

Add new job to governance daemon:

```typescript
// governance_daemon.ts
const WORK_QUEUE_CRON = '*/1 * * * *';  // Every minute

private async runWorkQueueCheck(): Promise<void> {
  // Check for timed-out jobs
  // Advance queue if slots available
  // Clean up stale entries
}
```

---

## Smoke Tests

1. **Admission Approved:** Request job when capacity available → APPROVED
2. **Admission Queued:** Request job at capacity → QUEUED with position
3. **Admission Denied:** Request in CLOSURE mode → DENIED
4. **Completion Frees Slot:** Complete job → slot freed, queue advances
5. **Dependency Block:** Request job with unmet dependency → QUEUED
6. **Dependency Unlock:** Complete dependency → dependent moves to active
7. **Timeout Handling:** Job exceeds timeout → auto-failed, slot freed
8. **Cancel Active:** Cancel running job → slot freed, queue advances
9. **Cancel Queued:** Cancel queued job → removed, positions updated
10. **Closure Unification:** AI job complete → appears in closures.json

---

## Implementation Order

1. **Work Ledger schema + file initialization**
2. **POST /api/work/request** — admission gate
3. **POST /api/work/complete** — completion handler
4. **GET /api/work/status** — status query
5. **POST /api/work/cancel** — cancellation
6. **Daemon job** — queue advancement + timeout handling
7. **Closure integration** — unified ledger writes
8. **Contract validation** — WorkLedger.v1.json enforcement

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `services/delta-kernel/src/core/work-controller.ts` | NEW: Work admission logic |
| `services/delta-kernel/src/api/server.ts` | MODIFY: Add 4 endpoints |
| `services/delta-kernel/src/governance/governance_daemon.ts` | MODIFY: Add queue check job |
| `services/cognitive-sensor/work_ledger.json` | NEW: Ledger data file |
| `contracts/schemas/WorkLedger.v1.json` | NEW: Schema |
| `services/cognitive-sensor/validate.py` | MODIFY: Add validate_work_ledger() |

---

## What This Enables

The moment Phase 6A is live:

1. **AIs are under law** — they must ask permission, they must report completion
2. **Capacity is bounded** — no runaway parallelism, no overload
3. **Dependencies are enforced** — work happens in correct order
4. **Closure is unified** — human and AI work in same ledger
5. **Cost is trackable** — AI metrics flow through completion reports

---

## What Phase 6B Becomes

After 6A is stable:

- **Prep workers** — background jobs that ready work before human starts
- **Scheduling bots** — agents that plan future work
- **Multi-agent routing** — directing work to best-fit agents
- **Predictive loading** — pre-running likely-needed jobs

All of these become **clients of the work controller**.

---

*Phase 6A: First you make law apply to machines. Then machines become safe to automate.*
