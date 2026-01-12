# Delta-State Fabric v0 — Inbox + Messaging Delta Flow

**Status:** LOCKED
**Version:** 0.1.0

---

## 1. Unified Inbox Entity

There is exactly **one Inbox entity**.

```json
Inbox {
  "unread_count": 0,
  "priority_queue": ["thread_id"],
  "task_queue": ["task_id"],
  "idea_queue": ["note_id"],
  "last_activity_at": "timestamp"
}
```

Everything enters the system through the Inbox.

---

## 2. Creating a Thread

User starts a new conversation.

### Create Thread Entity

Delta:

```json
PATCH: [
  { "op": "add", "path": "/title", "value": "General" },
  { "op": "add", "path": "/participants", "value": ["me"] },
  { "op": "add", "path": "/unread_count", "value": 0 },
  { "op": "add", "path": "/priority", "value": "NORMAL" },
  { "op": "add", "path": "/task_flag", "value": false }
]
```

---

## 3. Sending a Message (Delta-Native)

Messages are stored as **template_id + params** only.

### Create Message Entity

```json
Message {
  "thread_id": "T1",
  "template_id": "TEMPLATE_HELLO",
  "params": { "name": "Alex" },
  "sender": "me",
  "status": "SENT"
}
```

---

## 4. Update Thread State

Delta to Thread:

```json
PATCH: [
  { "op": "replace", "path": "/last_message_id", "value": "M1" },
  { "op": "replace", "path": "/unread_count", "value": 1 }
]
```

---

## 5. Update Inbox State

Delta to Inbox:

```json
PATCH: [
  { "op": "replace", "path": "/last_activity_at", "value": NOW },
  { "op": "add", "path": "/priority_queue/0", "value": "T1" },
  { "op": "replace", "path": "/unread_count", "value": 1 }
]
```

---

## 6. Reading a Message

User opens thread.

### Delta to Thread:

```json
PATCH: [
  { "op": "replace", "path": "/unread_count", "value": 0 }
]
```

### Delta to Inbox:

```json
PATCH: [
  { "op": "replace", "path": "/unread_count", "value": 0 }
]
```

---

## 7. Auto-Task Creation (System Rule)

If message template is in `TASK_TRIGGER_SET`, system auto-creates a Task.

Example trigger: `TEMPLATE_REQUEST_CALL`

### Create Task Entity:

```json
Task {
  "title_template": "TEMPLATE_CALL",
  "title_params": { "name": "Alex" },
  "status": "OPEN",
  "priority": "NORMAL",
  "linked_thread": "T1"
}
```

Delta to Thread:

```json
PATCH: [
  { "op": "replace", "path": "/task_flag", "value": true }
]
```

Delta to Inbox:

```json
PATCH: [
  { "op": "add", "path": "/task_queue/0", "value": "Task7" }
]
```

---

## 8. LoRa / Low-Bandwidth Sync

Only the following deltas are transmitted:

- New Message entity deltas
- Thread state deltas
- Inbox deltas
- Task creation deltas

No blobs. No screens. No heavy payloads.

All traffic is **state-delta only**.
