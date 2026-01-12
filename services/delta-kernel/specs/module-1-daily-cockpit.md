# MODULE 1 — DAILY MODE SCREEN (COCKPIT)

**Status:** LOCKED
**Version:** 1.0.0

---

## Design Law

- Single fixed layout
- Mode-adaptive emphasis only (no layout switching)
- Terminal-grid hybrid (dense, text-first, no card clutter)
- Command cockpit, not lifestyle app
- Delta-driven re-render (no polling)
- Executable with confirmation gate

---

## Screen Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ██ DELTA FABRIC ██                          [RECOVER] 06:42    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MODE: CLOSE_LOOPS                                              │
│  ════════════════                                               │
│  sleep: OK (6.5h) │ loops: LOW (5) │ assets: LOW │ money: OK    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  PREPARED ACTIONS                              [7 max]          │
│  ─────────────────                                              │
│  [1] ► Reply: Alex re: contract (HIGH)                          │
│  [2] ► Complete: Send invoice to Sarah                          │
│  [3] ► Complete: Review PR #142                                 │
│  [4] ► Reply: Team standup thread                               │
│  [5] ► Complete: Update project status                          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  TOP TASKS                                                      │
│  ─────────────                                                  │
│  [!] Call Alex (OVERDUE) ───────────────────────── HIGH         │
│  [ ] Send weekly report ─────────────────────────── NORMAL      │
│  [ ] Review Q1 metrics ──────────────────────────── NORMAL      │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  DRAFTS                                        [READY: 2]       │
│  ──────                                                         │
│  [M] Message draft → Alex (re: meeting)         ░░░░░░░░ READY  │
│  [A] Asset draft → Weekly summary               ░░░░░░░░ QUEUED │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  NEXT LEVERAGE MOVES                           [LUT-derived]    │
│  ───────────────────                                            │
│  → Close 4 loops to unlock BUILD mode                           │
│  → Invoice pending ($2,400) would flip money to HIGH            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [Enter #] Execute  [D] Drafts  [S] Signals  [Q] Queue  [?] Help│
└─────────────────────────────────────────────────────────────────┘
```

---

## UI State Schema

```typescript
interface CockpitState {
  // Header
  timestamp: Timestamp;

  // Mode Section
  mode: Mode;
  signals: SignalDisplaySet;
  mode_since: Timestamp;

  // Prepared Actions (max 7)
  prepared_actions: PreparedAction[];

  // Top Tasks (mode-sorted)
  top_tasks: TaskDisplay[];

  // Drafts
  drafts: DraftDisplay[];

  // Leverage Moves (LUT-derived only)
  leverage_moves: LeverageMove[];

  // Pending confirmation
  pending_action: PendingAction | null;

  // Render metadata
  last_delta_id: UUID;
  render_version: number;
}

interface SignalDisplaySet {
  sleep_hours: SignalDisplay;
  open_loops: SignalDisplay;
  assets_shipped: SignalDisplay;
  deep_work_blocks: SignalDisplay;
  money_delta: SignalDisplay;
}

interface SignalDisplay {
  raw: number;
  bucket: 'LOW' | 'OK' | 'HIGH';
  label: string;
  is_critical: boolean;  // Triggers mode override
}

interface PreparedAction {
  slot: number;           // 1-7
  action_id: UUID;
  action_type: ActionType;
  label: string;
  entity_id: UUID;
  priority: Priority;
  is_overdue: boolean;
}

type ActionType =
  | 'reply_message'
  | 'complete_task'
  | 'send_draft'
  | 'apply_automation'
  | 'create_asset'
  | 'delegate'
  | 'rest_action';

interface TaskDisplay {
  task_id: UUID;
  title: string;          // Rendered from template
  priority: Priority;
  due_at: Timestamp | null;
  is_overdue: boolean;
  mode_relevance: number; // 0-100, higher = more relevant to current mode
}

interface DraftDisplay {
  draft_id: UUID;
  draft_type: 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM';
  label: string;
  target_entity_id: UUID | null;
  status: 'READY' | 'QUEUED' | 'APPLIED';
}

interface LeverageMove {
  move_id: string;
  description: string;
  impact: string;
  trigger_condition: string;  // What would activate this
}

interface PendingAction {
  pending_id: UUID;
  action: PreparedAction;
  created_at: Timestamp;
  expires_at: Timestamp;     // Auto-cancel after timeout
  confirm_prompt: string;
}
```

---

## Entity Schemas

### Draft Entity

```typescript
interface DraftData {
  draft_type: 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM';
  template_id: string;
  params: Record<string, string>;
  target_entity_id: UUID | null;
  status: 'READY' | 'QUEUED' | 'APPLIED';
  created_by: 'user' | 'system' | 'ai';
  mode_context: Mode;        // Mode when draft was created
}
```

### PendingAction Entity

```typescript
interface PendingActionData {
  action_type: ActionType;
  target_entity_id: UUID;
  payload: Record<string, unknown>;
  status: 'PENDING' | 'CONFIRMED' | 'CANCELLED' | 'EXPIRED';
  created_at: Timestamp;
  expires_at: Timestamp;
  confirmed_at: Timestamp | null;
}
```

### LeverageMove (Not an entity — computed from LUT)

```typescript
interface LeverageMoveRule {
  rule_id: string;
  condition: (signals: BucketedSignals, mode: Mode) => boolean;
  description: string;
  impact: string;
  trigger_hint: string;
}
```

---

## Delta Flows

### 1. User Selects Action → Create PendingAction

```
User Input: [1]
↓
Create PendingAction Entity
↓
Delta: {
  patch: [
    { op: "add", path: "/action_type", value: "reply_message" },
    { op: "add", path: "/target_entity_id", value: "T1" },
    { op: "add", path: "/status", value: "PENDING" },
    { op: "add", path: "/expires_at", value: NOW + 30000 }
  ]
}
↓
Cockpit shows confirmation prompt
```

### 2. User Confirms → Execute + Clear Pending

```
User Input: [Y] or [Enter]
↓
Read PendingAction
↓
Execute actual action (creates real deltas)
↓
Update PendingAction: status → CONFIRMED
↓
Clear from cockpit
```

### 3. User Cancels or Timeout → Expire Pending

```
User Input: [N] or timeout
↓
Update PendingAction: status → CANCELLED | EXPIRED
↓
Clear from cockpit
```

### 4. Draft Applied → Update Draft Status

```
Draft confirmed
↓
Execute draft (Message send, Asset create, etc.)
↓
Delta to Draft: status → APPLIED
```

### 5. Signal Change → Mode May Change

```
Any signal delta
↓
Route check: computeNextMode(current, buckets)
↓
If mode changed:
  Delta to SystemState: mode → new_mode
↓
Cockpit re-renders (actions filtered, tasks re-sorted)
```

---

## Rendering Rules

### Rule 1: Mode Gating

```typescript
function filterActionsByMode(actions: PreparedAction[], mode: Mode): PreparedAction[] {
  return actions.filter(a => ACTION_MODE_MAP[a.action_type].includes(mode));
}
```

Actions not legal for current mode **do not exist** on screen.

### Rule 2: Task Sorting

```typescript
function sortTasksForMode(tasks: TaskDisplay[], mode: Mode): TaskDisplay[] {
  return tasks.sort((a, b) => {
    // 1. Mode relevance (higher first)
    if (a.mode_relevance !== b.mode_relevance) {
      return b.mode_relevance - a.mode_relevance;
    }
    // 2. Priority
    if (a.priority !== b.priority) {
      return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
    }
    // 3. Due date (earlier first, null last)
    if (a.due_at !== b.due_at) {
      if (a.due_at === null) return 1;
      if (b.due_at === null) return -1;
      return a.due_at - b.due_at;
    }
    return 0;
  });
}
```

### Rule 3: Mode Relevance Calculation

```typescript
const TASK_MODE_RELEVANCE: Record<Mode, (task: TaskData) => number> = {
  RECOVER: (t) => t.priority === 'LOW' ? 100 : 20,
  CLOSE_LOOPS: (t) => t.linked_thread ? 100 : 80,
  BUILD: (t) => t.title_template.includes('CREATE') ? 100 : 50,
  COMPOUND: (t) => t.title_template.includes('EXTEND') ? 100 : 50,
  SCALE: (t) => t.title_template.includes('DELEGATE') ? 100 : 30,
};
```

### Rule 4: Leverage Moves (LUT Only)

```typescript
const LEVERAGE_MOVE_RULES: LeverageMoveRule[] = [
  {
    rule_id: 'loops_to_build',
    condition: (s, m) => m === 'CLOSE_LOOPS' && s.open_loops === 'LOW',
    description: 'Close loops to unlock BUILD mode',
    impact: 'Enables asset creation',
    trigger_hint: 'Complete or block pending tasks',
  },
  {
    rule_id: 'money_flip',
    condition: (s, m) => s.money_delta === 'OK',
    description: 'Pending revenue would flip money to HIGH',
    impact: 'Unlocks SCALE mode path',
    trigger_hint: 'Send invoices, close deals',
  },
  // ... more rules
];
```

### Rule 5: Prepared Actions Limit

Hard cap at 7. If more exist, take top 7 by:
1. Overdue first
2. Priority
3. Creation time (older first)

### Rule 6: Delta-Driven Render

```typescript
function onDelta(delta: Delta, cockpit: CockpitState): CockpitState {
  // Track which entities changed
  const affected = getAffectedEntities(delta);

  // Rebuild only affected sections
  let next = { ...cockpit };

  if (affected.includes('system_state')) {
    next = rebuildModeSection(next);
    next = rebuildPreparedActions(next);  // Mode change affects filtering
    next = rebuildTopTasks(next);         // Mode change affects sorting
    next = rebuildLeverageMoves(next);
  }

  if (affected.includes('task')) {
    next = rebuildTopTasks(next);
    next = rebuildPreparedActions(next);
  }

  if (affected.includes('draft')) {
    next = rebuildDrafts(next);
  }

  if (affected.includes('thread') || affected.includes('message')) {
    next = rebuildPreparedActions(next);
  }

  if (affected.includes('pending_action')) {
    next = rebuildPendingAction(next);
  }

  next.last_delta_id = delta.delta_id;
  next.render_version++;

  return next;
}
```

---

## Component Breakdown

```
Cockpit
├── HeaderBar
│   ├── Logo
│   ├── ModeIndicator (quick glance)
│   └── Clock
│
├── ModeSection
│   ├── CurrentMode (large)
│   └── SignalStrip (horizontal)
│
├── PreparedActionsSection
│   ├── ActionSlot[1-7]
│   └── (empty slots hidden)
│
├── TopTasksSection
│   ├── TaskRow (repeating)
│   └── (max visible: configurable)
│
├── DraftsSection
│   ├── DraftRow (repeating)
│   └── StatusBadge
│
├── LeverageMovesSection
│   └── MoveRow (repeating)
│
├── ConfirmationOverlay (when pending_action exists)
│   ├── ActionPreview
│   ├── ConfirmButton
│   └── CancelButton
│
└── CommandBar
    └── KeyHints
```

---

## Confirmation Gate Protocol

1. User selects action slot (1-7)
2. System creates PendingAction entity with 30s expiry
3. Overlay shows action preview + confirm/cancel
4. On confirm: execute action, emit deltas, mark CONFIRMED
5. On cancel/timeout: mark CANCELLED/EXPIRED
6. Overlay clears, cockpit re-renders

**No action executes without passing through confirmation gate.**

---

## Mode-Adaptive Emphasis

| Mode | Emphasized | Muted |
|------|-----------|-------|
| RECOVER | rest actions, low-priority tasks | asset creation, delegation |
| CLOSE_LOOPS | reply actions, linked tasks | create actions |
| BUILD | create actions, unlinked tasks | reply actions |
| COMPOUND | extend actions | create new |
| SCALE | delegate actions | direct execution |

Emphasis = visual weight (brighter, first position)
Muted = reduced opacity, lower position
Hidden = illegal actions not rendered at all
