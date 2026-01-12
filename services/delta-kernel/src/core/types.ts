/**
 * Delta-State Fabric v0 — Core Type Definitions
 *
 * LOCKED - These types are the foundation. Do not modify without versioning.
 */

// === PRIMITIVES ===

export type UUID = string;
export type Timestamp = number; // Unix epoch ms
export type SHA256 = string;

// === ENUMS ===

export type EntityType =
  | 'message'
  | 'thread'
  | 'task'
  | 'note'
  | 'project'
  | 'system_state'
  | 'inbox'
  | 'draft'
  | 'pending_action'
  | 'token'
  | 'pattern'
  | 'motif'
  | 'discovery_proposal'
  | 'design_proposal'
  | 'ui_surface'
  | 'ui_component'
  | 'ui_render_tick'
  | 'ui_surface_link'
  | 'camera_surface'
  | 'scene_tile'
  | 'scene_object'
  | 'scene_light'
  | 'camera_tick'
  | 'actuator'
  | 'actuator_state'
  | 'control_surface'
  | 'control_widget'
  | 'actuation_intent'
  | 'actuation_receipt'
  | 'audio_surface';

export type Mode =
  | 'RECOVER'
  | 'CLOSE_LOOPS'
  | 'BUILD'
  | 'COMPOUND'
  | 'SCALE';

export type Author = 'user' | 'system' | 'ai' | 'cognitive-sensor' | 'enforcement_system' | 'closure_engine' | 'governance_daemon';

export type Priority = 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';

export type MessageStatus = 'SENT' | 'DELIVERED' | 'READ';

export type TaskStatus = 'OPEN' | 'DONE' | 'BLOCKED' | 'IN_PROGRESS' | 'ARCHIVED';

export type ProjectStatus = 'ACTIVE' | 'PAUSED' | 'DONE';

// === CORE TABLES ===

export interface Entity {
  entity_id: UUID;
  entity_type: EntityType;
  created_at: Timestamp;
  current_version: number;
  current_hash: SHA256;
  is_archived: boolean;
}

export interface Delta {
  delta_id: UUID;
  entity_id: UUID;
  timestamp: Timestamp;
  author: Author;
  patch: JsonPatch[];
  prev_hash: SHA256;
  new_hash: SHA256;
}

// JSON Patch (RFC 6902)
export interface JsonPatch {
  op: 'add' | 'remove' | 'replace' | 'move' | 'copy' | 'test';
  path: string;
  value?: unknown;
  from?: string;
}

// === BASE TYPE FOR INDEX SIGNATURE COMPATIBILITY ===

export interface BaseEntityData {
  [key: string]: unknown;
}

// === ENTITY STATE TYPES ===

export interface SystemStateData extends BaseEntityData {
  mode: Mode;
  signals?: {
    sleep_hours: number;
    open_loops: number;
    assets_shipped: number;
    deep_work_blocks: number;
    money_delta: number;
  };
  // Flat fields (alternative to signals object, used by API)
  sleep_hours?: number;
  open_loops?: number;
  assets_shipped?: number;
  deep_work_blocks?: number;
  money_delta?: number;
  leverage_balance?: number;
  streak_days?: number;
}

export interface ThreadData extends BaseEntityData {
  title: string;
  participants: UUID[];
  last_message_id: UUID | null;
  unread_count: number;
  priority: Priority;
  task_flag: boolean;
}

export interface MessageData extends BaseEntityData {
  thread_id: UUID;
  template_id: string;
  params: Record<string, string>;
  sender: UUID;
  status: MessageStatus;
}

export interface TaskData extends BaseEntityData {
  title?: string;
  title_template?: string;
  title_params?: Record<string, string>;
  status: TaskStatus;
  priority: Priority;
  due_at?: Timestamp | null;
  linked_thread?: UUID | null;
  created_at?: Timestamp;
  closed_at?: Timestamp | null;
  project_id?: UUID | null;
  parent_task_id?: UUID | null;
  template_id?: string | null;
  params?: Record<string, unknown>;
}

export interface NoteData extends BaseEntityData {
  template_id: string;
  params: Record<string, string>;
  tags: string[];
}

export interface ProjectData extends BaseEntityData {
  name_template: string;
  name_params: Record<string, string>;
  status: ProjectStatus;
  task_ids: UUID[];
}

// === TEMPLATE DICTIONARY ===

export interface Template {
  template_id: string;
  slots: string[];
  pattern: string;
}

// === INBOX ===

export interface InboxData extends BaseEntityData {
  unread_count: number;
  priority_queue: UUID[];
  task_queue: UUID[];
  idea_queue: UUID[];
  last_activity_at: Timestamp;
}

// === DRAFT ===

export type DraftType = 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM';

export type DraftStatus = 'READY' | 'QUEUED' | 'APPLIED' | 'DISMISSED' | 'PENDING';

export interface DraftData extends BaseEntityData {
  draft_type: DraftType;
  template_id: string;
  params: Record<string, string>;
  target_entity_id: UUID | null;
  source_entity_id?: UUID | null;
  fingerprint?: SHA256;
  status: DraftStatus;
  created_by: Author;
  mode_context: Mode;
  created_at?: Timestamp;
  expires_at?: Timestamp | null;
  summary?: string;
}

// === PENDING ACTION ===

export type ActionType =
  | 'reply_message'
  | 'complete_task'
  | 'send_draft'
  | 'apply_automation'
  | 'create_asset'
  | 'delegate'
  | 'rest_action';

export type PendingActionStatus = 'PENDING' | 'CONFIRMED' | 'CANCELLED' | 'EXPIRED';

export interface PendingActionData extends BaseEntityData {
  action_type: ActionType;
  target_entity_id: UUID;
  payload: Record<string, unknown>;
  status: PendingActionStatus;
  created_at: Timestamp;
  expires_at: Timestamp;
  confirmed_at: Timestamp | null;
}

// === MATRYOSHKA DICTIONARY (Compression Tiers) ===

// Tier 1: Token Dictionary — atomic units
export interface TokenData extends BaseEntityData {
  token_id: string;
  value: string;
  frequency: number;
  created_at: Timestamp;
}

// Tier 2: Pattern Dictionary — sequences of tokens
export interface PatternData extends BaseEntityData {
  pattern_id: string;
  token_sequence: string[]; // token_ids
  frequency: number;
  created_at: Timestamp;
}

// Tier 3: Motif Dictionary — sequences of patterns
export interface MotifData extends BaseEntityData {
  motif_id: string;
  pattern_sequence: string[]; // pattern_ids
  slots: string[]; // parameter slots in this motif
  frequency: number;
  created_at: Timestamp;
}

// Compressed content reference
export interface CompressedContent {
  type: 'token' | 'pattern' | 'motif';
  ref_id: string;
  params?: Record<string, string>;
}

// === VECTOR DISCOVERY (Module 4) ===

export type DiscoveryProposalType =
  | 'PATTERN_PROMOTION'
  | 'MOTIF_PROMOTION'
  | 'TEMPLATE_SUGGESTION'
  | 'ROUTING_SUGGESTION'
  | 'ANOMALY';

export type DiscoveryProposalStatus = 'NEW' | 'REVIEWED' | 'ACCEPTED' | 'REJECTED';

export interface DiscoveryProposalData extends BaseEntityData {
  proposal_type: DiscoveryProposalType;
  source_entity_ids: UUID[];
  proposed_structure: ProposedStructure;
  confidence: number; // 0.0 – 1.0
  fingerprint: SHA256;
  status: DiscoveryProposalStatus;
  created_at: Timestamp;
  reviewed_at: Timestamp | null;
  review_notes: string | null;
}

// Discriminated union for proposed structures
export type ProposedStructure =
  | PatternPromotionStructure
  | MotifPromotionStructure
  | TemplateSuggestionStructure
  | RoutingSuggestionStructure
  | AnomalyStructure;

export interface PatternPromotionStructure {
  type: 'PATTERN_PROMOTION';
  token_sequence: string[];
  suggested_pattern_id: string;
  example_texts: string[];
}

export interface MotifPromotionStructure {
  type: 'MOTIF_PROMOTION';
  pattern_sequence: string[];
  suggested_motif_id: string;
  slots: string[];
}

export interface TemplateSuggestionStructure {
  type: 'TEMPLATE_SUGGESTION';
  suggested_template_id: string;
  pattern: string;
  slots: string[];
  mode_restriction: Mode | null;
}

export interface RoutingSuggestionStructure {
  type: 'ROUTING_SUGGESTION';
  issue_type: 'LOOP_DETECTED' | 'SKIP_DETECTED' | 'STUCK_MODE' | 'DRIFT';
  description: string;
  affected_modes: Mode[];
  suggested_fix: string;
}

export interface AnomalyStructure {
  type: 'ANOMALY';
  anomaly_type: 'NOVEL_LANGUAGE' | 'UNUSUAL_FLOW' | 'BLOCKED_LOOP' | 'OUTLIER';
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
}

// === AI DESIGN LAYER (Module 5) ===

export type DesignProposalType =
  | 'NEW_TEMPLATE'
  | 'ROUTING_PATCH'
  | 'WORKFLOW_SUGGESTION'
  | 'AUTOMATION_RULE'
  | 'DICTIONARY_SEED';

export type DesignProposalStatus = 'NEW' | 'REVIEWED' | 'ACCEPTED' | 'REJECTED';

export interface DesignProposalData extends BaseEntityData {
  proposal_type: DesignProposalType;
  description: string;
  proposed_structure: DesignStructure;
  source_discovery_ids: UUID[]; // Links to DiscoveryProposals that informed this
  confidence: number; // 0.0 – 1.0
  fingerprint: SHA256;
  status: DesignProposalStatus;
  designed_by: AIRole;
  created_at: Timestamp;
  reviewed_at: Timestamp | null;
  review_notes: string | null;
  compiled_at: Timestamp | null; // When accepted and compiled into LUT
}

// AI Roles (isolated design agents)
export type AIRole = 'linguist' | 'architect' | 'automator' | 'synthesizer';

// Discriminated union for design structures
export type DesignStructure =
  | NewTemplateStructure
  | RoutingPatchStructure
  | WorkflowSuggestionStructure
  | AutomationRuleStructure
  | DictionarySeedStructure;

export interface NewTemplateStructure {
  type: 'NEW_TEMPLATE';
  template_id: string;
  pattern: string;
  slots: string[];
  mode_restriction: Mode | null;
  example_renderings: string[];
}

export interface RoutingPatchStructure {
  type: 'ROUTING_PATCH';
  target_mode: Mode;
  condition_changes: RoutingConditionPatch[];
  rationale: string;
}

export interface RoutingConditionPatch {
  signal: keyof SystemStateData['signals'];
  current_threshold: string;
  proposed_threshold: string;
  effect: string;
}

export interface WorkflowSuggestionStructure {
  type: 'WORKFLOW_SUGGESTION';
  trigger_conditions: Record<string, string>;
  actions: WorkflowAction[];
  mode_applicability: Mode[];
}

export interface WorkflowAction {
  action_type: 'create_draft' | 'suggest_template' | 'flag_priority' | 'schedule_review';
  parameters: Record<string, string>;
}

export interface AutomationRuleStructure {
  type: 'AUTOMATION_RULE';
  rule_id: string;
  trigger_entity_type: EntityType;
  trigger_conditions: Record<string, unknown>;
  derived_action_type: ActionType;
  action_template: Record<string, unknown>;
}

export interface DictionarySeedStructure {
  type: 'DICTIONARY_SEED';
  seed_type: 'token' | 'pattern' | 'motif';
  proposed_entries: DictionarySeedEntry[];
}

export interface DictionarySeedEntry {
  id: string;
  value: string | string[]; // string for token, string[] for pattern/motif
  slots?: string[];
  source_examples: string[];
}

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

// === TYPE MAP ===

export type EntityDataMap = {
  system_state: SystemStateData;
  thread: ThreadData;
  message: MessageData;
  task: TaskData;
  note: NoteData;
  project: ProjectData;
  inbox: InboxData;
  draft: DraftData;
  pending_action: PendingActionData;
  token: TokenData;
  pattern: PatternData;
  motif: MotifData;
  discovery_proposal: DiscoveryProposalData;
  design_proposal: DesignProposalData;
  ui_surface: UISurfaceData;
  ui_component: UIComponentStateData;
  ui_render_tick: UIRenderTickData;
  ui_surface_link: UISurfaceLinkData;
  camera_surface: CameraSurfaceData;
  scene_tile: SceneTileData;
  scene_object: SceneObjectData;
  scene_light: SceneLightData;
  camera_tick: CameraTickData;
  actuator: ActuatorData;
  actuator_state: ActuatorStateData;
  control_surface: ControlSurfaceData;
  control_widget: ControlWidgetData;
  actuation_intent: ActuationIntentData;
  actuation_receipt: ActuationReceiptData;
};

// === UI SURFACE STREAMING (Module 8) ===

// UI Component Kinds (bounded set)
export type UIComponentKind =
  | 'TEXT'
  | 'GAUGE'
  | 'CHART'
  | 'LIST'
  | 'INDICATOR'
  | 'BUTTON';

// Component State Indicator (shared across kinds)
export type UIStateIndicator = 'OK' | 'WARN' | 'ALERT';

// UI Text Style
export type UITextStyle = 'PLAIN' | 'BOLD' | 'MUTED';

// UI Surface (a "screen")
export interface UISurfaceData extends BaseEntityData {
  name: string;
  schema_version: '0.1.0';
  root_component_id: UUID;
  created_at: Timestamp;
}

// UI Component State (each widget instance)
export interface UIComponentStateData extends BaseEntityData {
  surface_id: UUID;
  kind: UIComponentKind;
  props: UIComponentProps;
  created_at: Timestamp;
}

// Discriminated union for component props (schema-bounded)
export type UIComponentProps =
  | UITextProps
  | UIGaugeProps
  | UIChartProps
  | UIListProps
  | UIIndicatorProps
  | UIButtonProps;

// TEXT props
export interface UITextProps {
  kind: 'TEXT';
  text: string;
  style: UITextStyle;
}

// GAUGE props
export interface UIGaugeProps {
  kind: 'GAUGE';
  label: string;
  value: number;
  min: number;
  max: number;
  unit: string;
  state: UIStateIndicator;
}

// CHART props (append-only series)
export interface UIChartProps {
  kind: 'CHART';
  title: string;
  series: {
    name: string;
    points: number[];
  };
  window: number; // Max points to keep
}

// LIST props (keyed items)
export interface UIListItem {
  id: string;
  text: string;
  state: UIStateIndicator;
}

export interface UIListProps {
  kind: 'LIST';
  title: string;
  items: UIListItem[];
}

// INDICATOR props
export interface UIIndicatorProps {
  kind: 'INDICATOR';
  label: string;
  on: boolean;
  state: UIStateIndicator;
}

// BUTTON props (for remote control surfaces)
export interface UIButtonProps {
  kind: 'BUTTON';
  label: string;
  enabled: boolean;
  action_id: string;
}

// UI Render Tick (optional grouping marker)
export interface UIRenderTickData extends BaseEntityData {
  surface_id: UUID;
  tick: number;
  created_at: Timestamp;
}

// UI Surface Link (who is mirroring whom)
export type UISurfaceLinkStatus = 'ACTIVE' | 'PAUSED' | 'CLOSED';

export interface UISurfaceLinkData extends BaseEntityData {
  surface_id: UUID;
  sender_node_id: UUID;
  receiver_node_id: UUID;
  status: UISurfaceLinkStatus;
  created_at: Timestamp;
}

// Stream Metrics (for proving ultra-low bandwidth)
export interface StreamMetrics {
  deltas_sent: number;
  bytes_sent: number;
  avg_bytes_per_delta: number;
  max_delta_bytes: number;
  deltas_received: number;
  bytes_received: number;
  dropped_or_rejected: number;
}

// Allowed UI Delta Operations (streaming contract)
export type UIStreamOp =
  | 'REPLACE_SCALAR'    // Replace number/string/boolean/enum
  | 'APPEND_POINT'      // Add to chart points array
  | 'ADD_LIST_ITEM'     // Add keyed item to list
  | 'REPLACE_LIST_ITEM' // Replace keyed item in list
  | 'REMOVE_LIST_ITEM'  // Remove keyed item from list
  | 'REPLACE_STATE'     // Replace state field (OK|WARN|ALERT)
  | 'REPLACE_ENABLED';  // Replace enabled flag

// === CAMERA TILE DELTA STREAMING (Module 9) ===

// Camera Surface (a camera scene)
export interface CameraSurfaceData extends BaseEntityData {
  name: string;
  grid_w: number;           // Grid width in tiles
  grid_h: number;           // Grid height in tiles
  tile_size: number;        // Tile size in pixels
  created_at: Timestamp;
}

// Scene Tile State (static or residual tile)
export interface SceneTileData extends BaseEntityData {
  surface_id: UUID;
  x: number;                // Grid x position
  y: number;                // Grid y position
  hash: SHA256;             // Content hash (baseline or residual)
  brightness: number;       // -8..+8 adjustment
  chroma: number;           // -8..+8 adjustment
  is_residual: boolean;     // true if changed from baseline
  created_at: Timestamp;
}

// Scene Object State (moving objects)
export interface SceneObjectData extends BaseEntityData {
  surface_id: UUID;
  shape_tiles: UUID[];      // References to SceneTileData
  x: number;                // Current position
  y: number;
  vx: number;               // Velocity
  vy: number;
  brightness: number;       // Object brightness adjustment
  visible: boolean;
  created_at: Timestamp;
}

// Scene Light Region
export type LightRegion = 'GLOBAL' | {
  x: number;
  y: number;
  w: number;
  h: number;
};

// Scene Light State (global or regional lighting)
export interface SceneLightData extends BaseEntityData {
  surface_id: UUID;
  region: LightRegion;
  brightness: number;       // -16..+16
  color_temp: number;       // Kelvin (e.g., 2700 warm, 6500 daylight)
  created_at: Timestamp;
}

// Camera Tick (optional grouping marker)
export interface CameraTickData extends BaseEntityData {
  surface_id: UUID;
  tick: number;
  created_at: Timestamp;
}

// Camera Stream Metrics
export interface CameraStreamMetrics {
  deltas_sent: number;
  bytes_sent: number;
  avg_bytes_per_delta: number;
  residual_tiles_emitted: number;
  object_updates: number;
  light_updates: number;
}

// Allowed Camera Delta Operations (streaming contract)
export type CameraStreamOp =
  | 'REPLACE_POSITION'      // Replace x, y, vx, vy
  | 'REPLACE_BRIGHTNESS'    // Replace brightness
  | 'REPLACE_CHROMA'        // Replace chroma
  | 'REPLACE_COLOR_TEMP'    // Replace color_temp
  | 'REPLACE_HASH'          // Replace tile hash (residual)
  | 'ADD_SHAPE_TILE'        // Add to shape_tiles
  | 'REMOVE_SHAPE_TILE'     // Remove from shape_tiles
  | 'REPLACE_VISIBLE';      // Replace visibility

// === REMOTE CONTROL + ACTUATION DELTAS (Module 10) ===

// Actuator Kinds (controllable device types)
export type ActuatorKind =
  | 'RELAY'
  | 'SERVO'
  | 'MOTOR'
  | 'VALVE'
  | 'DIMMER'
  | 'SOFTWARE_TOGGLE'
  | 'SOFTWARE_PARAM';

// Actuator Definition (a controllable thing)
export interface ActuatorData extends BaseEntityData {
  name: string;
  kind: ActuatorKind;
  owner_node_id: UUID;          // Device that can physically execute
  capabilities: {
    min?: number;
    max?: number;
    step?: number;
    allowed_values?: (number | string)[];
  };
  created_at: Timestamp;
}

// Actuator State (measured/confirmed state)
export type ActuatorStateValue = 'UNKNOWN' | 'OFF' | 'ON' | 'MOVING' | 'ERROR';

export interface ActuatorStateData extends BaseEntityData {
  actuator_id: UUID;
  owner_node_id: UUID;
  state: ActuatorStateValue;
  value?: number | string;      // e.g., dimmer %, servo angle
  last_applied_intent_id?: UUID; // Idempotency anchor
  updated_at: Timestamp;
}

// Control Surface (UI control panel)
export interface ControlSurfaceData extends BaseEntityData {
  name: string;
  schema_version: '0.1.0';
  created_at: Timestamp;
}

// Control Widget Kinds
export type ControlWidgetKind = 'BUTTON' | 'TOGGLE' | 'SLIDER' | 'SELECT';

// Control Widget (button/slider/toggle mapped to actuator)
export interface ControlWidgetData extends BaseEntityData {
  surface_id: UUID;
  kind: ControlWidgetKind;
  label: string;
  target_actuator_id: UUID;
  props: {
    confirm: boolean;           // Require user confirm at terminal
    min?: number;
    max?: number;
    step?: number;
    options?: (number | string)[];
  };
  created_at: Timestamp;
}

// Actuation Intent Status
export type ActuationIntentStatus =
  | 'NEW'
  | 'AUTHORIZED'
  | 'DENIED'
  | 'EXPIRED'
  | 'DISPATCHED'
  | 'APPLIED'
  | 'FAILED';

// Actuation Action Types
export type ActuationAction = 'SET_ON' | 'SET_OFF' | 'SET_VALUE';

// Actuation Intent (requested change; NOT execution)
export interface ActuationIntentData extends BaseEntityData {
  actuator_id: UUID;
  requested_by_node_id: UUID;
  requested_by_actor: Author;
  request: {
    action: ActuationAction;
    value?: number | string;
  };
  policy: {
    requires_human_confirm: boolean;
    ttl_ms: number;             // Default 30_000
  };
  status: ActuationIntentStatus;
  reason?: string;
  created_at: Timestamp;
  expires_at: Timestamp;
}

// Actuation Outcome
export type ActuationOutcome = 'APPLIED' | 'FAILED';

// Actuation Receipt (proof of execution)
export interface ActuationReceiptData extends BaseEntityData {
  intent_id: UUID;
  actuator_id: UUID;
  owner_node_id: UUID;
  outcome: ActuationOutcome;
  observed_state: {
    state: ActuatorStateValue;
    value?: number | string;
  };
  created_at: Timestamp;
}

// Control Metrics (for proving actuation correctness)
export interface ControlMetrics {
  intents_created: number;
  intents_authorized: number;
  intents_denied: number;
  intents_applied: number;
  intents_failed: number;
  median_time_to_apply_ms: number;
  duplicates_prevented: number;
}

// Allowed Actuation Delta Operations (streaming contract)
export type ActuationStreamOp =
  | 'REPLACE_STATUS'        // Replace intent status
  | 'REPLACE_STATE'         // Replace actuator state
  | 'REPLACE_VALUE'         // Replace actuator value
  | 'SET_REASON';           // Set denial/failure reason
