# MODULE 7 — OFF-GRID NODES

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Minimal hardware runtime for physical deployment on radios, batteries, solar, and mesh networks.

> This is what turns Delta Fabric into an infrastructure organism.

---

## Node Classes

| Class | CPU | Storage | Display | Radio | Capabilities |
|-------|-----|---------|---------|-------|--------------|
| CORE | Full | 32+ GB | Full LCD | Multi | All modules |
| EDGE | Embedded | 64 MB - 8 GB | Grid LCD | LoRa | Cockpit shell + sync |
| MICRO | Micro | 2-4 MB | 4-line LCD | LoRa | Message/task shell only |

---

## Hardware Profiles

### CORE Class
```typescript
raspberry_pi_4: {
  cpu_class: 'full',
  storage_mb: 32000,
  has_display: true,
  display_type: 'full',
  has_radio: true,
  radio_type: 'multi',
  battery_powered: false,
  solar_capable: true,
}

laptop: {
  cpu_class: 'full',
  storage_mb: 256000,
  display_type: 'full',
  radio_type: 'wifi',
  battery_powered: true,
}
```

### EDGE Class
```typescript
raspberry_pi_zero: {
  cpu_class: 'embedded',
  storage_mb: 8000,
  display_type: 'lcd_grid',
  radio_type: 'lora',
  battery_powered: true,
  solar_capable: true,
}

esp32_lora: {
  cpu_class: 'embedded',
  storage_mb: 64,
  display_type: 'lcd_grid',
  radio_type: 'lora',
  battery_powered: true,
  solar_capable: true,
}

old_android: {
  cpu_class: 'embedded',
  storage_mb: 2000,
  display_type: 'full',
  radio_type: 'multi',
  battery_powered: true,
}
```

### MICRO Class
```typescript
esp8266: {
  cpu_class: 'micro',
  storage_mb: 4,
  has_display: false,
  display_type: 'none',
  radio_type: 'lora',
  battery_powered: true,
  solar_capable: true,
}

rp2040_lora: {
  cpu_class: 'micro',
  storage_mb: 2,
  display_type: 'lcd_4line',
  radio_type: 'lora',
  battery_powered: true,
  solar_capable: true,
}
```

---

## Runtime Capabilities

```typescript
NODE_CAPABILITIES: Record<NodeClass, RuntimeCapabilities> = {
  CORE: {
    routing: true,
    preparation: true,
    dictionary: true,
    vector_discovery: true,
    ai_design: true,
    full_sync: true,
    full_ui: true,
  },
  EDGE: {
    routing: true,
    preparation: false,  // No prep engine
    dictionary: false,   // No dictionary
    vector_discovery: false,
    ai_design: false,
    full_sync: true,
    full_ui: false,     // Shell only
  },
  MICRO: {
    routing: false,
    preparation: false,
    dictionary: false,
    vector_discovery: false,
    ai_design: false,
    full_sync: false,   // Limited sync
    full_ui: false,     // Minimal display
  },
};
```

---

## Storage Limits

```typescript
STORAGE_LIMITS: Record<NodeClass, { max_entities: number; max_deltas: number }> = {
  CORE: { max_entities: 100000, max_deltas: 1000000 },
  EDGE: { max_entities: 1000, max_deltas: 10000 },
  MICRO: { max_entities: 100, max_deltas: 1000 },
};
```

---

## Supported Entity Types

```typescript
SUPPORTED_ENTITY_TYPES: Record<NodeClass, EntityType[]> = {
  CORE: [/* all entity types */],
  EDGE: [
    'system_state', 'pending_action', 'task', 'draft', 'message', 'thread',
    'actuation_intent', 'actuator', 'actuator_state', 'actuation_receipt',
  ],
  MICRO: [
    'system_state', 'pending_action', 'task', 'message',
    'actuation_intent', 'actuator_state', 'actuation_receipt',
  ],
};
```

---

## Power Management

### Power States
```typescript
type PowerState = 'ACTIVE' | 'IDLE' | 'DEEP_SLEEP' | 'RADIO_BURST' | 'CHARGING';
```

### State Transitions
| From | To | Trigger |
|------|-----|---------|
| ACTIVE | IDLE | 30s idle |
| IDLE | DEEP_SLEEP | 5 min idle (battery only) |
| DEEP_SLEEP | RADIO_BURST | Radio receive |
| DEEP_SLEEP | ACTIVE | Timer wake |
| * | CHARGING | Power connected |

```typescript
IDLE_TIMEOUT_MS = 30000;        // 30 seconds
DEEP_SLEEP_TIMEOUT_MS = 300000; // 5 minutes
DEFAULT_WAKE_INTERVAL_MS = 3600000; // 1 hour
```

### Power Functions
```typescript
function updatePowerState(config, currentTime): NodeRuntimeConfig
function wakeNode(config, reason: 'radio' | 'timer' | 'user'): NodeRuntimeConfig
function enterDeepSleep(config): NodeRuntimeConfig
function shouldWake(config, currentTime): boolean
```

---

## Storage Management

```typescript
interface StorageBudget {
  total_bytes: number;
  entities_bytes: number;
  deltas_bytes: number;
  watermarks_bytes: number;
  conflicts_bytes: number;
  lut_bytes: number;
  available_bytes: number;
}

function calculateStorageBudget(nodeClass, entities, deltas, storageMb): StorageBudget
function isStorageAvailable(nodeClass, currentEntities, currentDeltas): boolean
function canStoreEntityType(nodeClass, entityType): boolean
```

---

## Cockpit Shell (EDGE Nodes)

Minimal UI for constrained displays.

```typescript
interface CockpitShellState {
  mode_display: Mode;
  selected_index: number;
  visible_actions: ShellAction[];
  visible_tasks: ShellTaskItem[];
  visible_drafts: ShellDraftItem[];
  leverage_hint: string | null;
  status_line: string;
  last_refresh_at: Timestamp;
}

MAX_SHELL_ACTIONS = 7;
MAX_SHELL_TASKS = 5;
MAX_SHELL_DRAFTS = 3;
```

### Shell Actions
```typescript
interface ShellAction {
  index: number;           // 1-7 for keypad
  action_type: 'apply_draft' | 'confirm_action' | 'complete_task';
  label: string;
  target_entity_id: UUID;
  requires_confirm: boolean;
}
```

### Shell Display
```
MODE: BUILD

ACTIONS:
>[1] Apply: REPLY to email
 [2] Confirm: send_message
 [3] Complete: Review docs

TASKS:
*! Fix critical bug
   Update documentation
   Write tests

DRAFTS:
  • REPLY: EMAIL_FOLLOW_UP

LEVERAGE:
  • Ship small win

---
3 actions | 3 tasks
```

### Input Handling
```typescript
type ShellInput = '1' | '2' | '3' | '4' | '5' | '6' | '7' | 'Y' | 'N' | 'UP' | 'DOWN';

interface ShellInputResult {
  action: ShellAction | null;
  confirmed: boolean;
  newState: CockpitShellState;
}

function handleShellInput(state, input): ShellInputResult
```

---

## Micro Shell (MICRO Nodes)

4-line LCD display only.

```typescript
interface MicroShellState {
  message_count: number;
  task_count: number;
  pending_count: number;
  last_sync_at: Timestamp | null;
  display_lines: string[];  // 4 lines max
}
```

### Micro Display
```
M:3 T:5 P:1
Sync: 14:30
ACTION PENDING
---
```

---

## Radio Burst Profile

LoRa sync session for battery-constrained nodes.

```typescript
interface RadioBurstSession {
  session_id: UUID;
  peer_node_id: UUID | null;
  phase: RadioBurstPhase;
  started_at: Timestamp;
  packets_sent: number;
  packets_received: number;
  bytes_transmitted: number;
  rssi: number | null;
  snr: number | null;
}

type RadioBurstPhase = 'IDLE' | 'HELLO' | 'HEADS' | 'WANT' | 'DELTAS' | 'ACK' | 'COMPLETE' | 'ERROR';
```

### Burst Flow
```
IDLE → HELLO → HEADS → WANT → DELTAS → ACK → COMPLETE
  ↑                                              ↓
  └──────────────── (on error) ──────────────────┘
```

```typescript
async function runBurstStep(
  session: RadioBurstSession,
  localNode: SyncNode,
  localEntities: Map<UUID, Entity>,
  localDeltas: Map<UUID, Delta[]>,
  entityTypes: Map<UUID, EntityType>,
  peerPacket: SyncPacket | null
): Promise<BurstPacketResult>
```

---

## Node Lifecycle

```typescript
interface NodeLifecycle {
  boot: () => void;
  tick: (deltaMs: number) => void;
  onRadioReceive: (packet: SyncPacket) => void;
  onUserInput: (input: ShellInput) => void;
  shutdown: () => void;
}

function createNodeLifecycle(
  config: NodeRuntimeConfig,
  syncNode: SyncNode,
  onStateChange: (config: NodeRuntimeConfig) => void
): NodeLifecycle
```

---

## Entity Filtering

```typescript
function filterEntitiesForNodeClass(
  nodeClass: NodeClass,
  entities: Array<{ entity: Entity; entityType: EntityType }>
): Array<{ entity: Entity; entityType: EntityType }>

function filterDeltasForNodeClass(
  nodeClass: NodeClass,
  deltas: Delta[],
  entityTypes: Map<UUID, EntityType>
): Delta[]
```

---

## Node Creation

```typescript
function createNodeRuntime(nodeClass, hardwareProfile): NodeRuntimeConfig
function createCoreNode(hardware?): NodeRuntimeConfig   // Default: Pi 4
function createEdgeNode(hardware?): NodeRuntimeConfig   // Default: ESP32
function createMicroNode(hardware?): NodeRuntimeConfig  // Default: ESP8266
```

---

## Files

| File | Purpose |
|------|---------|
| `off-grid-node.ts` | Full implementation (~800 lines) |

---

## Key Functions

| Function | Purpose |
|----------|---------|
| `createNodeRuntime()` | Initialize node config |
| `updatePowerState()` | Manage power transitions |
| `wakeNode()` | Wake from sleep |
| `enterDeepSleep()` | Enter low-power mode |
| `calculateStorageBudget()` | Track storage usage |
| `createCockpitShellState()` | Build EDGE UI state |
| `renderCockpitShell()` | Render to text |
| `handleShellInput()` | Process keypad input |
| `createMicroShellState()` | Build MICRO UI state |
| `createRadioBurstSession()` | Start sync session |
| `runBurstStep()` | Execute sync step |
| `createNodeLifecycle()` | Full lifecycle manager |
| `filterEntitiesForNodeClass()` | Filter by capability |

---

## Deployment Scenarios

### Solar Field Station
- EDGE node (ESP32 + LoRa)
- Solar panel + battery
- Periodic sync every hour
- Task queue for field work

### Remote Relay
- MICRO node (ESP8266)
- Message forwarding only
- Deep sleep between bursts
- Months on battery

### Mobile Operator
- EDGE node (old Android)
- Full cockpit shell
- WiFi + LoRa fallback
- Action confirmation

### Base Station
- CORE node (Pi 4)
- Always-on, AC power
- Full prep + AI design
- Multi-radio (WiFi + LoRa)

---

## Next: Module 8 — UI Streaming

Dashboard mirroring over deltas.

Command: **Continue to Module 8 — UI Streaming.**
