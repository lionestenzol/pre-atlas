# Agent Substrate — machine onboarding contract

Campaign III (SUBSTRATE) of `ATLAS_MASTER_PLAN.md`, task 01_contract. This is
the doc a fresh agent session should be able to follow, with zero other
context, to go from nothing to claim → heartbeat → complete on a real job.
Every request/response shape below was exercised live against the running
delta-kernel instance while writing this doc, not copied from source and
assumed correct.

If you are an agent reading this to onboard yourself: **do the numbered
steps in order.** Steps 1-4 are the loop every agent runs. Step 5-6 are what
you need to know exists but usually don't call directly.

## The one rule that doesn't bend

Read `TRUST_BOUNDARY.md` before anything else. Short version: the set of
things an agent can *do* (`ActionType` in `services/delta-kernel/src/core/types-core.ts`)
and the set of commands UASC will execute (`services/uasc-executor/storage/schema.sql`)
are closed by source. Fleet growth means more **tenants** (data — a new agent
identity), never more **verbs** (code — a new action type). Nothing in this
doc, and nothing you do as an onboarded agent, changes that set. If a task
seems to require a capability that isn't already wired, that's a "propose a
source change to a human," not a "register it at runtime."

## Step 1 — get a bearer token

```
GET http://localhost:3001/api/auth/token
→ { "ok": true, "token": "<hex>" }
```

No auth required on this one route (and `/health`, `/services/health`,
`/cli/manifest*`) — everything else under `/api/*` needs
`Authorization: Bearer <token>` once `.aegis-tenant-key` exists (dev mode
with no key file skips auth entirely, same token either way).

## Step 2 — find out what's live

Don't hardcode ports or routes. Use the atlas-map MCP (or its REST twin,
atlas-map-api on :3072) to discover the current surface:

- `atlas_describe_list()` — every surface that exists
- `atlas_describe(surface, role="agent")` — what that surface can do, scoped
  to what an agent is cleared to see (deliberately less than a human operator)
- `atlas_call(surface, capability, args)` — invoke by name; the gateway
  resolves surface → port so you never need to know delta-kernel is on :3001

Full model in `services/atlas-map-api/SELF_DESCRIBE.md`.

## Step 3 — the work loop (the part you'll actually run in a cycle)

Four calls, in this order, repeated for as long as you're doing autonomous
work:

**3a. Request permission to start a job**

```
POST /api/work/request
{ "type": "ai" | "system", "title": "...", "agent": "<your label>",
  "weight"?: 1, "timeout_ms"?: 600000, "metadata"?: { "cmd": "..." } }
→ { "status": "APPROVED" | "QUEUED" | "DENIED", "job_id": "...", ... }
```

`type: "system"` bypasses the `build_allowed` gate (used for infra/governance
work); `type: "ai"` is denied in CLOSURE mode unless the ledger config allows
it. A job only becomes *claimable* (step 3b) if `metadata.cmd` is set — that's
what marks it as an autonomously-executable task rather than a work-queue
entry a human is expected to close by hand.

**3b. Claim the job**

```
POST /api/work/claim
{ "executor_id": "<your stable identity — see Identity below>" }
→ { "claimed": true, "executor_id": "...", "job": { "job_id": "...", ... } }
  | { "claimed": false, "executor_id": "...", "job": null }
```

Claims are atomic and exclusive — one executor holds a job at a time. A claim
has a TTL (job's own `timeout_ms`, or 15 min default, minimum 5s). If you stop
heartbeating and the claim expires, a *different* executor can claim the same
job next (this increments `attempts` on the claim, visible in
`GET /api/work/metrics`).

**3c. Heartbeat while you work**

```
POST /api/work/heartbeat
{ "job_id": "...", "executor_id": "...", "extension_ms"?: 600000 }
→ { "extended": true, "job_id": "...", "executor_id": "...", "new_expires_at": <ms> }
  | { "extended": false, ... }  (404 if job/executor mismatch)
```

Call this periodically (well under the claim TTL) for anything that takes
longer than a few seconds. `extended: false` means you lost the claim —
someone/something else has it now, stop working on it.

**3d. Report completion**

```
POST /api/work/complete
{ "job_id": "...", "outcome": "completed" | "failed" | "abandoned",
  "result"?: {...}, "error"?: "...", "metrics"?: { "duration_ms", "tokens_used", "cost_usd" } }
→ { "success": true, "job_id": "...", "outcome": "...", "duration_ms": ..., "queue_advanced": bool, ... }
```

This is the ledger write. `GET /api/work/history` and the timeline
(`GET /api/signals`, or step 4 below) are how this becomes visible to
everything else in the system — a job isn't "done" until this call lands.

## Step 4 — watch the queue without polling (added this campaign)

`GET /api/work/subscribe` is a Server-Sent Events stream of work-queue
timeline events (`WORK_REQUESTED`, `WORK_APPROVED`, `WORK_QUEUED`,
`WORK_COMPLETED`, `WORK_FAILED`, `WORK_RETRIED`, `WORK_TIMEOUT`,
`WORK_CANCELLED`, `AUTO_EXECUTED`) as they happen. Open one connection
(regular HTTP GET with the same bearer header, not a browser-only
`EventSource` — this is meant for agent/service clients) instead of polling
`/api/work/status` in a loop. It's backed by an in-process pub-sub inside
`TimelineLogger`, not NATS — no broker, no Docker dependency, and it only
sees events from the delta-kernel instance you're connected to.

```
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:3001/api/work/subscribe
: connected

event: WORK_APPROVED
data: {"id":"e_...","ts":"...","type":"WORK_APPROVED","source":"work_controller","data":{...}}
```

NATS event emission (`emitEvent()` in `event-emitter.ts`) also exists for
cross-service pushes and degrades gracefully with no broker running — SSE
is the zero-infra option for "watch my own work queue."

## Step 5 — what happens if your job times out

A job that blows its `timeout_ms` doesn't die immediately anymore. It gets
`max_retry_attempts` (ledger config, default 3) chances — retried in place
with a fresh clock and a cleared claim, so a different executor can pick it
up — before it's allowed to fail terminally with
`outcome: "failed", error: "Job timed out after N retries"`. You'll see
`WORK_RETRIED` events on the SSE stream and `stats.total_retried` climb in
`GET /api/work/status`. This is bounded — it will not retry forever.

## Identity: what `agent` / `executor_id` mean today, and tenancy

Right now, `agent` (a free-text label on the job, shown in the ledger and
`/api/work/status`) and `executor_id` (the claim holder, shown as
`claimed_by`) are both just strings you choose — there's no registry
enforcing that "codex-worker-3" is really codex-worker-3. That's fine for a
single trusted operator; it's not fine for a fleet of untrusted or
semi-trusted agents.

**Real scoped identity exists, but a human has to switch it on per agent —
you cannot self-provision.** aegis-fabric (:3002) already has a tenant
registry (`services/aegis-fabric/src/tenants/tenant-registry.ts`) with a
`POST /api/v1/tenants` route that mints a real API key per tenant. It's
gated behind `X-API-Key: <AEGIS_ADMIN_KEY>` — an env-var-only admin secret,
never handed to an agent, never derivable from anything an agent can read.
An operator runs:

```
POST http://localhost:3002/api/v1/tenants
X-API-Key: <AEGIS_ADMIN_KEY>
{ "name": "agent-<your label>", "tier": "FREE" }
→ { "tenant_id": "...", "api_key": "<hex>", ... }
```

...once per agent identity, out of band, and hands you the resulting
`api_key` through whatever channel provisioned you in the first place. Use
that same label as your `agent`/`executor_id` string in the work-queue calls
above so ledger attribution lines up with the tenant record. This is why
provisioning a tenant is a human action, not something this doc walks an
agent through calling itself — see the trust-boundary rule at the top.

`ATLAS_USER_ID` (delta-kernel, default `'bruke'`) is already
env-overridable per-process — not currently per-agent-request, just noted
here so it isn't mistaken for a missing feature.

## DoD for this doc

A fresh agent session, given only this file (and `TRUST_BOUNDARY.md`),
completes one full request → claim → heartbeat → complete cycle against the
real running delta-kernel, and shows up correctly attributed in
`GET /api/work/history`.
