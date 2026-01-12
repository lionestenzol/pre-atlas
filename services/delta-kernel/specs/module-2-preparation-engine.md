# MODULE 2 — PREPARATION ENGINE

**Status:** LOCKED
**Version:** 1.0.0

---

## Mission

Deterministic background workers that **prepare** (never execute) work outputs based on:
- Current `SystemState.mode`
- Current entities (threads/tasks/notes/projects)
- Recent deltas

Outputs: `Draft` entities, `LeverageMove` selections, `PreparedAction` candidates.
Execution requires `PendingAction` confirmation gate.

---

## Laws

### No Direct Changes to Operational Entities

The Preparation Engine may NOT directly modify:
- Task.status
- Thread state
- SystemState.mode
- Inbox queues

It may ONLY create/update:
- `Draft` entities
- `LeverageMove` records

### Idempotent by Design

Every draft has a deterministic `fingerprint`.
Running engine 100 times on same state = no duplicates.

---

## Template Catalog (12 Templates)

### Generic Structural (6) — Any Mode

| ID | Purpose | Pattern |
|----|---------|---------|
| TEMPLATE_ACK | Acknowledge | "Acknowledged." |
| TEMPLATE_DEFER | Defer with boundary | "I'll follow up {window}." |
| TEMPLATE_REQUEST | Ask for something | "Can you send {item}?" |
| TEMPLATE_UPDATE | Status update | "Update: {status}." |
| TEMPLATE_CLOSE | Close a loop | "Closing this thread." |
| TEMPLATE_FOLLOWUP | Follow up | "Following up on {topic}." |

### Mode-Tagged (6) — Mode-Specific Only

| ID | Mode | Purpose | Pattern |
|----|------|---------|---------|
| TEMPLATE_RECOVER_REST | RECOVER | Health boundary | "I'm offline until {time} to recover." |
| TEMPLATE_CLOSE_COMMIT | CLOSE_LOOPS | Commit time | "I will resolve this by {time}." |
| TEMPLATE_BUILD_OUTLINE | BUILD | Asset outline | "Here is the outline for {asset}." |
| TEMPLATE_COMPOUND_EXTEND | COMPOUND | Extend asset | "Extending {asset} with {addition}." |
| TEMPLATE_SCALE_DELEGATE | SCALE | Delegate | "Please take ownership of {task}." |
| TEMPLATE_SCALE_SYSTEMIZE | SCALE | Systemize | "Systemizing {process}." |

### Enforcement

- Mode-tagged templates MUST match current Mode
- Generic templates may appear in any Mode
- No other templates legal in v0

---

## Draft Entity (Final v0 Shape)

```typescript
DraftData {
  draft_type: 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM';
  template_id: string;
  params: Record<string, string>;
  target_entity_id: UUID | null;
  source_entity_id: UUID | null;
  fingerprint: SHA256;
  status: 'READY' | 'QUEUED' | 'APPLIED' | 'DISMISSED';
  created_by: Author;
  mode_context: Mode;
  created_at: Timestamp;
  expires_at: Timestamp | null;
}
```

---

## Worker Topology

### Trigger Model: Delta-Driven Only

Engine runs when:
- Any Delta committed affecting relevant sections
- Mode changes (SystemState delta)
- New messages/tasks/notes created

No timers. No polling.

### Workers (v0 Set)

1. `ModeRefreshWorker`
2. `ThreadTriageWorker`
3. `TaskTriageWorker`
4. `DraftGeneratorWorker`
5. `LeverageMoveSelector`

---

## Worker Responsibilities

### 1. ModeRefreshWorker

**Input:** SystemState deltas
**Output:** Triggers other workers on mode change

- If `mode` changed → trigger ThreadTriage, TaskTriage, DraftGenerator

### 2. ThreadTriageWorker

**Input:** Threads with unread_count > 0 OR priority HIGH/CRITICAL OR task_flag = true
**Output:** MESSAGE drafts (never sends)

Selection (top 5):
1. Priority
2. Unread count
3. Recency

Draft templates per mode:
- CLOSE_LOOPS: `TEMPLATE_CLOSE_COMMIT`, `TEMPLATE_ACK`
- BUILD: `TEMPLATE_DEFER`
- RECOVER: `TEMPLATE_RECOVER_REST`

### 3. TaskTriageWorker

**Input:** OPEN tasks
**Output:** PLAN drafts, ordering cues

Mode relevance LUT:
- RECOVER: health/admin/light tasks, due soon
- CLOSE_LOOPS: replies/finishes/cleanup
- BUILD: tasks linked to ACTIVE projects
- COMPOUND: tasks extending shipped assets
- SCALE: delegate/systemize/acquire tasks

### 4. DraftGeneratorWorker

**Factory for 4 draft types:**

A) MESSAGE drafts — from ThreadTriage
B) PLAN drafts — from task/project states
C) ASSET drafts — BUILD/COMPOUND only
D) SYSTEM drafts — SCALE only

**Hard caps (v0):**
- Max drafts visible in cockpit: 12
- Max drafts created per run: 5
- Drafts have `expires_at` for RECOVER/CLOSE_LOOPS (24h default)

### 5. LeverageMoveSelector

**Pure LUT lookup.** Not AI.

Input: mode + signal buckets
Output: 1-3 leverage moves max

---

## Fingerprint Calculation

```typescript
fingerprint = sha256(JSON.stringify({
  draft_type,
  template_id,
  target_entity_id,
  mode_context,
  // Key params only (not all)
  key_params: sortedKeyParams
}))
```

Prevents duplicate drafts for same context.

---

## Delta Flows

### Draft Creation (Engine Output)

```json
PATCH: [
  { "op": "add", "path": "/draft_type", "value": "MESSAGE" },
  { "op": "add", "path": "/template_id", "value": "TEMPLATE_CLOSE_COMMIT" },
  { "op": "add", "path": "/params", "value": { "time": "tomorrow 10am" } },
  { "op": "add", "path": "/target_entity_id", "value": "THREAD_T1" },
  { "op": "add", "path": "/fingerprint", "value": "abc123..." },
  { "op": "add", "path": "/status", "value": "READY" },
  { "op": "add", "path": "/expires_at", "value": 1767806400000 }
]
```

### Draft Dismissal

User action via cockpit:
- Draft status → DISMISSED

### Draft Apply

User confirms APPLY_DRAFT:
- Draft status → APPLIED
- Operational deltas emitted by confirmation flow (not engine)

---

## Expiration Rules

| Mode | Draft TTL |
|------|-----------|
| RECOVER | 24h |
| CLOSE_LOOPS | 24h |
| BUILD | 72h |
| COMPOUND | 72h |
| SCALE | No expiry |
