/**
 * Delta-State Fabric v0 — Sync & Off-Grid Type Definitions
 *
 * Types for Delta Sync Protocol (Module 6) and Off-Grid Nodes (Module 7).
 */

import type {
  UUID, Timestamp, SHA256, Mode, EntityType, Author,
  Delta, TaskStatus, DraftType,
} from './types-core.js';

// Re-export core for convenience
export type { UUID, Timestamp, SHA256 } from './types-core.js';

// === DELTA SYNC PROTOCOL (Module 6) ===

// Node Identity
export interface SyncNode {
  node_id: UUID;
  node_name: string;
  public_key: string; // Ed25519 public key
  created_at: Timestamp;
}

// Node Capabilities
export interface NodeCapabilities {
  max_packet_bytes: number;
  supports_cbor: boolean;
  supports_encryption: boolean;
  protocol_version: string;
}

// Peer Watermark (tracking sync state with each peer)
export interface PeerWatermark {
  peer_node_id: UUID;
  last_sync_at: Timestamp;
  entity_heads: Record<UUID, SHA256>; // entity_id -> current_hash
}

// Entity Head (advertised state)
export interface EntityHead {
  entity_id: UUID;
  entity_type: EntityType;
  current_hash: SHA256;
  current_version: number;
}

// Sync Packet Types
export type SyncPacketType = 'HELLO' | 'HEADS' | 'WANT' | 'DELTAS' | 'DELTAS_CHUNK' | 'ACK' | 'REJECT';

// Base packet structure
export interface SyncPacketBase {
  type: SyncPacketType;
  node_id: UUID;
  sig?: string; // Ed25519 signature over canonical payload
}

// HELLO packet
export interface HelloPacket extends SyncPacketBase {
  type: 'HELLO';
  protocol_version: string;
  caps: NodeCapabilities;
  nonce: string;
}

// HEADS packet
export interface HeadsPacket extends SyncPacketBase {
  type: 'HEADS';
  heads: EntityHead[];
}

// WANT request
export interface WantEntry {
  entity_id: UUID;
  since_hash: SHA256; // Request deltas after this hash
}

export interface WantPacket extends SyncPacketBase {
  type: 'WANT';
  wants: WantEntry[];
}

// DELTAS packet
export interface DeltasPacket extends SyncPacketBase {
  type: 'DELTAS';
  deltas: Delta[];
}

// DELTAS_CHUNK packet (for LoRa)
export interface DeltasChunkPacket extends SyncPacketBase {
  type: 'DELTAS_CHUNK';
  delta_id: UUID;
  chunk_index: number;
  chunk_total: number;
  chunk_payload: string; // Base64 encoded CBOR bytes
}

// ACK packet
export interface AckPacket extends SyncPacketBase {
  type: 'ACK';
  acked_delta_ids: UUID[];
}

// REJECT packet
export type RejectReason =
  | 'HASH_CHAIN_BROKEN'
  | 'SCHEMA_INVALID'
  | 'UNAUTHORIZED'
  | 'ENTITY_UNKNOWN'
  | 'SIGNATURE_INVALID';

export interface RejectPacket extends SyncPacketBase {
  type: 'REJECT';
  reason: RejectReason;
  details: {
    entity_id?: UUID;
    delta_id?: UUID;
    message?: string;
  };
}

// Union type for all packets
export type SyncPacket =
  | HelloPacket
  | HeadsPacket
  | WantPacket
  | DeltasPacket
  | DeltasChunkPacket
  | AckPacket
  | RejectPacket;

// Conflict (fork) tracking
export type ConflictStatus = 'DETECTED' | 'RESOLVING' | 'RESOLVED';

export interface EntityConflict {
  entity_id: UUID;
  base_hash: SHA256; // Common ancestor hash
  branch_a: {
    node_id: UUID;
    head_hash: SHA256;
    deltas: Delta[];
  };
  branch_b: {
    node_id: UUID;
    head_hash: SHA256;
    deltas: Delta[];
  };
  status: ConflictStatus;
  detected_at: Timestamp;
  resolved_at: Timestamp | null;
  resolution_delta_id: UUID | null;
}

// Sync session state
export type SyncSessionState =
  | 'HELLO_SENT'
  | 'HELLO_RECEIVED'
  | 'HEADS_EXCHANGED'
  | 'SYNCING'
  | 'COMPLETE'
  | 'ERROR';

export interface SyncSession {
  session_id: UUID;
  local_node_id: UUID;
  remote_node_id: UUID;
  state: SyncSessionState;
  started_at: Timestamp;
  completed_at: Timestamp | null;
  deltas_sent: number;
  deltas_received: number;
  conflicts_detected: number;
}

// Priority classes for LoRa transmission (Module 10 updated)
export type SyncPriority = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

export const SYNC_PRIORITY_MAP: Record<EntityType, SyncPriority> = {
  // 1. SystemState (highest priority)
  system_state: 1,
  // 2. PendingAction (user confirmations)
  pending_action: 2,
  // 3. ActuationIntent (control commands)
  actuation_intent: 3,
  // 4. ActuatorState / ActuationReceipt (device feedback)
  actuator_state: 4,
  actuation_receipt: 4,
  actuator: 4,
  // 5. Camera + Audio entities
  camera_surface: 5,
  scene_object: 5,
  scene_light: 5,
  scene_tile: 5,
  camera_tick: 5,
  audio_surface: 5,
  // 6. UI entities
  ui_surface: 6,
  ui_component: 6,
  ui_render_tick: 6,
  ui_surface_link: 6,
  control_surface: 6,
  control_widget: 6,
  // 7. Messages/Threads
  message: 7,
  thread: 7,
  // 8. Tasks/Projects
  task: 8,
  project: 8,
  // 9. Drafts/Notes/Inbox
  draft: 9,
  inbox: 9,
  note: 9,
  // 10. Proposals/Dictionary
  token: 10,
  pattern: 10,
  motif: 10,
  discovery_proposal: 10,
  design_proposal: 10,
  preparation_result: 9,
  cycle_board: 6,
  goal: 8,
};

// === OFF-GRID NODES (Module 7) ===

// Node class hierarchy
export type NodeClass = 'CORE' | 'EDGE' | 'MICRO';

// Hardware capabilities
export interface HardwareProfile {
  cpu_class: 'full' | 'embedded' | 'micro';
  storage_mb: number;
  has_display: boolean;
  display_type: 'none' | 'lcd_4line' | 'lcd_grid' | 'full';
  has_radio: boolean;
  radio_type: 'none' | 'lora' | 'ble' | 'wifi' | 'multi';
  battery_powered: boolean;
  solar_capable: boolean;
}

// Runtime capabilities per node class
export interface RuntimeCapabilities {
  cockpit_shell: boolean;
  preparation_engine: boolean;
  vector_discovery: boolean;
  ai_design: boolean;
  full_dictionary: boolean; // All tiers vs token-only
  conflict_resolution: boolean;
  leverage_moves: boolean;
}

// Node class capability matrix
export const NODE_CAPABILITIES: Record<NodeClass, RuntimeCapabilities> = {
  CORE: {
    cockpit_shell: true,
    preparation_engine: true,
    vector_discovery: true,
    ai_design: true,
    full_dictionary: true,
    conflict_resolution: true,
    leverage_moves: true,
  },
  EDGE: {
    cockpit_shell: true,
    preparation_engine: false, // Receives prepared drafts from CORE
    vector_discovery: false,
    ai_design: false,
    full_dictionary: true,
    conflict_resolution: true,
    leverage_moves: true,
  },
  MICRO: {
    cockpit_shell: false, // Minimal or no display
    preparation_engine: false,
    vector_discovery: false,
    ai_design: false,
    full_dictionary: false, // Token tier only
    conflict_resolution: false, // Forwards to EDGE/CORE
    leverage_moves: false,
  },
};

// Power state
export type PowerState = 'ACTIVE' | 'IDLE' | 'DEEP_SLEEP' | 'RADIO_BURST' | 'CHARGING';

// Node runtime configuration
export interface NodeRuntimeConfig {
  node_class: NodeClass;
  hardware: HardwareProfile;
  capabilities: RuntimeCapabilities;
  power_state: PowerState;
  wake_on_radio: boolean;
  wake_on_timer: boolean;
  wake_interval_ms: number | null; // null = no timer wake
  last_activity_at: Timestamp;
  uptime_ms: number;
}

// Cockpit Shell state (text grid interface)
export interface CockpitShellState {
  mode_display: Mode;
  selected_index: number;
  visible_actions: ShellAction[];
  visible_tasks: ShellTaskItem[];
  visible_drafts: ShellDraftItem[];
  leverage_hint: string | null;
  status_line: string;
  last_refresh_at: Timestamp;
}

// Shell action (confirmable item)
export interface ShellAction {
  index: number; // 1-7 for keypad selection
  action_type: 'apply_draft' | 'complete_task' | 'archive_task' | 'confirm_action' | 'signal_update';
  label: string;
  target_entity_id: UUID;
  requires_confirm: boolean;
}

// Shell task display item
export interface ShellTaskItem {
  entity_id: UUID;
  title: string;
  status: TaskStatus;
  priority_indicator: string; // "!" for HIGH, "" for normal
  is_overdue: boolean;
}

// Shell draft display item
export interface ShellDraftItem {
  entity_id: UUID;
  summary: string;
  draft_type: DraftType;
  is_expired: boolean;
}

// Radio burst session
export type RadioBurstPhase =
  | 'IDLE'
  | 'HELLO'
  | 'HEADS'
  | 'WANT'
  | 'DELTAS'
  | 'ACK'
  | 'COMPLETE'
  | 'ERROR';

export interface RadioBurstSession {
  session_id: UUID;
  peer_node_id: UUID | null;
  phase: RadioBurstPhase;
  started_at: Timestamp;
  packets_sent: number;
  packets_received: number;
  bytes_transmitted: number;
  rssi: number | null; // Signal strength
  snr: number | null; // Signal-to-noise ratio
}

// Node storage budget
export interface StorageBudget {
  total_bytes: number;
  entities_bytes: number;
  deltas_bytes: number;
  watermarks_bytes: number;
  conflicts_bytes: number;
  lut_bytes: number;
  available_bytes: number;
}

// Entity storage limits per node class
export const STORAGE_LIMITS: Record<NodeClass, { max_entities: number; max_deltas: number }> = {
  CORE: { max_entities: 100000, max_deltas: 1000000 },
  EDGE: { max_entities: 10000, max_deltas: 100000 },
  MICRO: { max_entities: 1000, max_deltas: 10000 },
};

// Entity types supported per node class
export const SUPPORTED_ENTITY_TYPES: Record<NodeClass, EntityType[]> = {
  CORE: [
    'system_state', 'thread', 'message', 'task', 'note', 'project',
    'inbox', 'draft', 'pending_action', 'token', 'pattern', 'motif',
    'discovery_proposal', 'design_proposal',
  ],
  EDGE: [
    'system_state', 'thread', 'message', 'task', 'note', 'project',
    'inbox', 'draft', 'pending_action', 'token', 'pattern', 'motif',
  ],
  MICRO: [
    'system_state', 'message', 'task', 'pending_action', 'token',
  ],
};
