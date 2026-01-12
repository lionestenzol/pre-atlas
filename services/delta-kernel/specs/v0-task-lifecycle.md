# Delta-State Fabric v0 — Task Lifecycle Flow

**Status:** LOCKED
**Version:** 0.1.0

---

## TASK STATES

```
OPEN → DONE → ARCHIVED
        ↘
         BLOCKED
```

All transitions are delta-driven.

---

## 1. Create Task

Created manually or via message automation.

```json
Task {
  "title_template": "TEMPLATE_FOLLOWUP",
  "title_params": { "name": "Alex" },
  "status": "OPEN",
  "priority": "NORMAL",
  "due_at": "2026-01-08T12:00",
  "linked_thread": "T1"
}
```

---

## 2. Surface Task in Inbox

Delta to Inbox:

```json
PATCH: [
  { "op": "add", "path": "/task_queue/0", "value": "Task7" }
]
```

---

## 3. Mark Task BLOCKED

Delta to Task:

```json
PATCH: [
  { "op": "replace", "path": "/status", "value": "BLOCKED" }
]
```

Delta to Inbox:

```json
PATCH: [
  { "op": "remove", "path": "/task_queue/0" }
]
```

---

## 4. Resume BLOCKED Task

Delta to Task:

```json
PATCH: [
  { "op": "replace", "path": "/status", "value": "OPEN" }
]
```

Delta to Inbox:

```json
PATCH: [
  { "op": "add", "path": "/task_queue/0", "value": "Task7" }
]
```

---

## 5. Complete Task (DONE)

Delta to Task:

```json
PATCH: [
  { "op": "replace", "path": "/status", "value": "DONE" }
]
```

Delta to Inbox:

```json
PATCH: [
  { "op": "remove", "path": "/task_queue/0" }
]
```

---

## 6. Archive Task (Auto / Manual)

Delta to Entity:

```json
PATCH: [
  { "op": "replace", "path": "/is_archived", "value": true }
]
```

Task is now cold storage.

---

## 7. Signal Update Hook

When a task is DONE, update SystemState:

Delta to SystemState:

```json
PATCH: [
  { "op": "replace", "path": "/signals/open_loops", "value": (open_loops - 1) }
]
```

This may trigger Markov routing change.

---

## 8. LoRa Sync Payload

Only deltas are transmitted:

- Task deltas
- Inbox deltas
- SystemState deltas

No task blobs.
