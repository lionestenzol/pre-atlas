/**
 * Delta-State Fabric v0 — Core Type Definitions
 *
 * Types actively used by the running system (server, daemon, routing, delta engine).
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
  | 'audio_surface'
  | 'preparation_result'
  | 'cycle_board';

export type Mode =
  | 'RECOVER'
  | 'CLOSURE'
  | 'MAINTENANCE'
  | 'BUILD'
  | 'COMPOUND'
  | 'SCALE';

export type Author = 'user' | 'system' | 'ai' | 'cognitive-sensor' | 'closure_engine' | 'preparation_engine' | 'governance_daemon' | 'cycleboard' | 'enforcement_system';

export type Priority = 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';

export type MessageStatus = 'SENT' | 'DELIVERED' | 'READ';

export type TaskStatus = 'OPEN' | 'IN_PROGRESS' | 'DONE' | 'BLOCKED' | 'ARCHIVED';

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

// === ENTITY STATE TYPES ===

// === LIFE SIGNAL TYPES ===

export type Bucket = 'LOW' | 'OK' | 'HIGH';

export type LifePhase = 1 | 2 | 3 | 4 | 5;
// 1=Stabilization, 2=Leverage Accumulation, 3=Extraction & Autonomy, 4=Scaling, 5=Generational Infrastructure

export interface EnergySignals {
  energy_level: number;       // 0-100 overall energy
  mental_load: number;        // 1-10 cognitive load
  sleep_quality: number;      // 1-5 last night
  burnout_risk: boolean;      // consecutive low-energy days
  red_alert_active: boolean;  // predicted interference window
}

export interface FinanceSignals {
  runway_months: number;      // months of expenses covered
  monthly_income: number;
  monthly_expenses: number;
  money_delta: number;        // net monthly change
}

export interface SkillsSignals {
  utilization_pct: number;    // % work aligned with top skills
  active_learning: boolean;   // studying/practicing this week
  mastery_count: number;      // skills at mastery level
  growth_count: number;       // skills being developed
}

export interface NetworkSignals {
  collaboration_score: number; // 0-100 collaboration health
  active_relationships: number;// interactions in last 30 days
  outreach_this_week: number;  // proactive outreach count
}

export interface LifeSignals {
  energy: EnergySignals;
  finance: FinanceSignals;
  skills: SkillsSignals;
  network: NetworkSignals;
  life_phase: LifePhase;
}

export interface SystemStateData {
  [key: string]: unknown;
  mode: Mode;
  signals: {
    sleep_hours: number;
    open_loops: number;
    assets_shipped: number;
    deep_work_blocks: number;
    money_delta: number;
  };
  life_signals?: LifeSignals;
}

export interface ThreadData {
  [key: string]: unknown;
  title: string;
  participants: UUID[];
  last_message_id: UUID | null;
  unread_count: number;
  priority: Priority;
  task_flag: boolean;
}

export interface MessageData {
  [key: string]: unknown;
  thread_id: UUID;
  template_id: string;
  params: Record<string, string>;
  sender: UUID;
  status: MessageStatus;
}

export interface TaskData {
  [key: string]: unknown;
  title_template: string;
  title_params: Record<string, string>;
  status: TaskStatus;
  priority: Exclude<Priority, 'CRITICAL'>;
  due_at: Timestamp | null;
  linked_thread: UUID | null;
}

export interface NoteData {
  [key: string]: unknown;
  template_id: string;
  params: Record<string, string>;
  tags: string[];
}

export interface ProjectData {
  [key: string]: unknown;
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

export interface InboxData {
  [key: string]: unknown;
  unread_count: number;
  priority_queue: UUID[];
  task_queue: UUID[];
  idea_queue: UUID[];
  last_activity_at: Timestamp;
}

// === DRAFT ===

export type DraftType = 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM';

export type DraftStatus = 'PENDING' | 'READY' | 'QUEUED' | 'APPLIED' | 'DISMISSED';

export interface DraftData {
  [key: string]: unknown;
  draft_type: DraftType;
  template_id: string;
  params: Record<string, string>;
  target_entity_id: UUID | null;
  source_entity_id: UUID | null;
  fingerprint: SHA256;
  summary?: string;
  status: DraftStatus;
  created_by: Author;
  mode_context: Mode;
  created_at: Timestamp;
  expires_at: Timestamp | null;
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

// Risk tiers for autonomous execution
export type RiskTier = 'auto' | 'notify' | 'confirm';

export type PendingActionStatus = 'PENDING' | 'CONFIRMED' | 'CANCELLED' | 'EXPIRED';

export interface PendingActionData {
  [key: string]: unknown;
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
export interface TokenData {
  [key: string]: unknown;
  token_id: string;
  value: string;
  frequency: number;
  created_at: Timestamp;
}

// Tier 2: Pattern Dictionary — sequences of tokens
export interface PatternData {
  [key: string]: unknown;
  pattern_id: string;
  token_sequence: string[]; // token_ids
  frequency: number;
  created_at: Timestamp;
}

// Tier 3: Motif Dictionary — sequences of patterns
export interface MotifData {
  [key: string]: unknown;
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
