/**
 * Delta-State Fabric v0 — Extended Type Definitions
 *
 * Types for Vector Discovery (Module 4), AI Design (Module 5),
 * UI Surface Streaming (Module 8), Camera Tile Streaming (Module 9),
 * Remote Control + Actuation (Module 10), and EntityDataMap.
 */

import type {
  UUID, Timestamp, SHA256, Mode, Author, EntityType,
  SystemStateData, ThreadData, MessageData, TaskData,
  NoteData, ProjectData, InboxData, DraftData, DraftType,
  PendingActionData, ActionType, TaskStatus,
  TokenData, PatternData, MotifData,
} from './types-core.js';

// Re-export core for convenience
export type { UUID, Timestamp, SHA256, Mode, Author, EntityType } from './types-core.js';

// === VECTOR DISCOVERY (Module 4) ===

export type DiscoveryProposalType =
  | 'PATTERN_PROMOTION'
  | 'MOTIF_PROMOTION'
  | 'TEMPLATE_SUGGESTION'
  | 'ROUTING_SUGGESTION'
  | 'ANOMALY';

export type DiscoveryProposalStatus = 'NEW' | 'REVIEWED' | 'ACCEPTED' | 'REJECTED';

export interface DiscoveryProposalData {
  [key: string]: unknown;
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

export interface DesignProposalData {
  [key: string]: unknown;
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
export interface UISurfaceData {
  name: string;
  schema_version: '0.1.0';
  root_component_id: UUID;
  created_at: Timestamp;
}

// UI Component State (each widget instance)
export interface UIComponentStateData {
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
export interface UIRenderTickData {
  surface_id: UUID;
  tick: number;
  created_at: Timestamp;
}

// UI Surface Link (who is mirroring whom)
export type UISurfaceLinkStatus = 'ACTIVE' | 'PAUSED' | 'CLOSED';

export interface UISurfaceLinkData {
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
export interface CameraSurfaceData {
  name: string;
  grid_w: number;           // Grid width in tiles
  grid_h: number;           // Grid height in tiles
  tile_size: number;        // Tile size in pixels
  created_at: Timestamp;
}

// Scene Tile State (static or residual tile)
export interface SceneTileData {
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
export interface SceneObjectData {
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
export interface SceneLightData {
  surface_id: UUID;
  region: LightRegion;
  brightness: number;       // -16..+16
  color_temp: number;       // Kelvin (e.g., 2700 warm, 6500 daylight)
  created_at: Timestamp;
}

// Camera Tick (optional grouping marker)
export interface CameraTickData {
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
export interface ActuatorData {
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

export interface ActuatorStateData {
  actuator_id: UUID;
  owner_node_id: UUID;
  state: ActuatorStateValue;
  value?: number | string;      // e.g., dimmer %, servo angle
  last_applied_intent_id?: UUID; // Idempotency anchor
  updated_at: Timestamp;
}

// Control Surface (UI control panel)
export interface ControlSurfaceData {
  name: string;
  schema_version: '0.1.0';
  created_at: Timestamp;
}

// Control Widget Kinds
export type ControlWidgetKind = 'BUTTON' | 'TOGGLE' | 'SLIDER' | 'SELECT';

// Control Widget (button/slider/toggle mapped to actuator)
export interface ControlWidgetData {
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
export interface ActuationIntentData {
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
export interface ActuationReceiptData {
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
  audio_surface: Record<string, unknown>;
  preparation_result: Record<string, unknown>;
  cycle_board: Record<string, unknown>;
};
