# Delta-State Fabric v0 — Core Schemas

**Status:** LOCKED
**Version:** 0.1.0

These are *not negotiable*. Everything builds on these.

---

## THE LAW OF THE SYSTEM

- No overwrites
- No raw blobs
- No uncontrolled AI execution
- Everything is delta
- Everything is routed through LUT modes

---

## ENTITY TABLE

Every object in the system is an Entity.

```json
Entity {
  "entity_id": "uuid",
  "entity_type": "message | thread | task | note | project | system_state",
  "created_at": "timestamp",
  "current_version": "int",
  "current_hash": "sha256",
  "is_archived": false
}
```

No object stores content directly.

---

## DELTA TABLE

Every change to an entity is a Delta.

```json
Delta {
  "delta_id": "uuid",
  "entity_id": "uuid",
  "timestamp": "timestamp",
  "author": "user | system | ai",
  "patch": [ JSON_PATCH ],
  "prev_hash": "sha256",
  "new_hash": "sha256"
}
```

Reconstruction = fold deltas in order.
Tamper-evident by default.

---

## SYSTEM STATE ENTITY

There is exactly one global system state entity:

```json
SystemState {
  "mode": "RECOVER | CLOSE_LOOPS | BUILD | COMPOUND | SCALE",
  "signals": {
    "sleep_hours": 0,
    "open_loops": 0,
    "assets_shipped": 0,
    "deep_work_blocks": 0,
    "money_delta": 0
  }
}
```

It is also modified only by deltas.

---

## MESSAGE THREAD ENTITY

```json
Thread {
  "title": "string",
  "participants": ["entity_id"],
  "last_message_id": "entity_id",
  "unread_count": 0,
  "priority": "LOW | NORMAL | HIGH | CRITICAL",
  "task_flag": false
}
```

---

## MESSAGE ENTITY

Messages are **template + params**, not raw text.

```json
Message {
  "thread_id": "entity_id",
  "template_id": "string",
  "params": { "slot": "value" },
  "sender": "entity_id",
  "status": "SENT | DELIVERED | READ"
}
```

---

## TASK ENTITY

```json
Task {
  "title_template": "template_id",
  "title_params": { "slot": "value" },
  "status": "OPEN | DONE | BLOCKED",
  "priority": "LOW | NORMAL | HIGH",
  "due_at": "timestamp",
  "linked_thread": "entity_id"
}
```

---

## NOTE ENTITY

```json
Note {
  "template_id": "string",
  "params": { "slot": "value" },
  "tags": ["string"]
}
```

---

## PROJECT ENTITY

```json
Project {
  "name_template": "template_id",
  "name_params": { },
  "status": "ACTIVE | PAUSED | DONE",
  "task_ids": ["entity_id"]
}
```

---

## TEMPLATE DICTIONARY (Matryoshka LUT Layer 1)

```json
Template {
  "template_id": "string",
  "slots": ["slot_name"],
  "pattern": "SEND {TYPE} TO GATE {X}"
}
```

Higher tiers (pattern / motif dictionaries) build later.
