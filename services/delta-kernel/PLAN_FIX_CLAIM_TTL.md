# Plan: Fix Execution Claim TTL to Prevent Duplicate Job Execution

## Problem

The work queue controller uses a hardcoded 5-minute TTL for execution claims. When an executor takes longer than 5 minutes to finish a job, the controller assumes the executor has crashed, releases the claim, and allows the same job to be claimed and executed again. This causes duplicate execution.

## Root Cause

One hardcoded constant:

```
File: src/core/work-controller.ts
Line: 219
Code: private readonly executionClaimTtlMs = 5 * 60 * 1000;
```

This value is used at line ~738 when computing `claim_expires_at`:

```
claim_expires_at: Date.now() + this.executionClaimTtlMs
```

The timeout check runs every 1 minute via governance daemon (`governance_daemon.ts` line 69, WORK_QUEUE_CRON). It calls `checkTimeouts()` (work-controller.ts lines 856-892) which fails any active job past its `timeout_at`.

## What Already Exists

The `WorkRequest` interface (work-controller.ts lines 91-100) already has a `timeout_ms` field:

```typescript
export interface WorkRequest {
  job_id?: string;
  type: JobType;
  title: string;
  agent?: string;
  weight?: number;
  depends_on?: string[];
  timeout_ms?: number;      // <-- THIS FIELD EXISTS BUT IS ONLY USED FOR JOB TIMEOUT, NOT CLAIM TTL
  metadata?: Record<string, unknown>;
}
```

Callers already send `timeout_ms` when submitting work. For example, `auto_actor.py` sends `"timeout_ms": 120000` and the UASC daemon test sent `"timeout_ms": 120000`.

## Changes Required

### Change 1: Use job timeout for claim TTL

**File:** `src/core/work-controller.ts`
**Method:** `claimNextExecutable()` (lines 716-770)
**What to change:** When computing `claim_expires_at`, use the job's `timeout_ms` if present. Fall back to the default 5-minute TTL if not.

Current (line ~738):
```typescript
claim_expires_at: Date.now() + this.executionClaimTtlMs
```

Change to:
```typescript
const jobTimeout = typeof job.timeout_ms === 'number' && job.timeout_ms > 0
  ? job.timeout_ms
  : this.executionClaimTtlMs;
claim_expires_at: Date.now() + jobTimeout
```

The `job` object here is an entry from the `active` array. You need to check how `timeout_ms` is stored on the job. Look at the `request()` method (around line 400) to see how `WorkRequest.timeout_ms` maps onto the stored job object. It likely sets `timeout_at` on the job. If `timeout_ms` is not stored directly, compute the claim TTL from `timeout_at - started_at` or pass `timeout_ms` through to the stored job.

### Change 2: Increase the default TTL

**File:** `src/core/work-controller.ts`  
**Line:** 219

Change:
```typescript
private readonly executionClaimTtlMs = 5 * 60 * 1000;
```

To:
```typescript
private readonly executionClaimTtlMs = 15 * 60 * 1000;
```

15 minutes is a safer default. Most UASC profiles have their own timeouts (EXECUTE_v1 has 300s = 5 minutes for the execute step). The claim TTL should always be longer than the execution timeout to avoid premature reclaim.

### Change 3 (optional, recommended): Add claim extension via heartbeat

This is not required for the immediate fix but prevents the problem permanently for very long jobs.

**File:** `src/core/work-controller.ts`  
**Add new method:** `extendClaim(jobId: string, executorId: string, extensionMs?: number)`

Logic:
1. Find the job in the active array
2. Verify the executor matches `metadata.execution.claimed_by`
3. Update `metadata.execution.claim_expires_at` to `Date.now() + (extensionMs || this.executionClaimTtlMs)`
4. Return success/failure

**File:** `src/api/server.ts`  
**Add endpoint:** `POST /api/work/heartbeat`

Body: `{ "job_id": "...", "executor_id": "..." }`  
Response: `{ "extended": true, "new_expires_at": <timestamp> }`

The UASC daemon (`services/uasc-executor/daemon.py`) would then call this endpoint periodically during long-running jobs. This is a separate follow-up task.

## Files to Modify

| File | Change |
|------|--------|
| `src/core/work-controller.ts` line 219 | Increase default TTL from 5 to 15 minutes |
| `src/core/work-controller.ts` lines ~736-741 | Use job timeout_ms for claim_expires_at |
| `src/api/server.ts` (optional) | Add POST /api/work/heartbeat endpoint |
| `src/core/work-controller.ts` (optional) | Add extendClaim() method |

## How to Verify

1. Submit a job with `"timeout_ms": 600000` (10 minutes)
2. Claim it via `POST /api/work/claim`
3. Check the returned `claim_expires_at` — it should be ~10 minutes from now, not 5
4. Wait 6 minutes without completing — the job should NOT be reclaimed
5. Complete the job — should succeed normally

## Do NOT Change

- The `checkTimeouts()` method logic (lines 856-892) — it correctly checks `timeout_at` on the job itself, which is separate from the claim TTL
- The WORK_QUEUE_CRON schedule (every 1 minute) — the check frequency is fine
- The UASC executor or daemon — the fix is entirely in delta-kernel
