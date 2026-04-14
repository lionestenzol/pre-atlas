/**
 * Aegis Delta Fabric — Shared Type Definitions
 *
 * Canonical types used by both Gateway and Kernel.
 * Source of truth for all entity types, enums, and interfaces.
 */

// === PRIMITIVES ===

export type UUID = string;
export type Timestamp = number; // Unix epoch ms
export type SHA256 = string;

// === MODE SYSTEM (mirrors delta-kernel) ===

export type Mode = 'RECOVER' | 'CLOSURE' | 'MAINTENANCE' | 'BUILD' | 'COMPOUND' | 'SCALE';

// === ENTITY SYSTEM ===

export type AegisEntityType =
  | 'aegis_tenant'
  | 'aegis_agent'
  | 'aegis_task'
  | 'aegis_policy'
  | 'aegis_approval'
  | 'aegis_webhook'
  | 'aegis_usage_record'
  | 'aegis_audit_entry';

export interface Entity {
  entity_id: UUID;
  entity_type: AegisEntityType;
  created_at: Timestamp;
  current_version: number;
  current_hash: SHA256;
  is_archived: boolean;
}

// === DELTA SYSTEM (RFC 6902 JSON Patch) ===

export interface JsonPatch {
  op: 'add' | 'replace' | 'remove';
  path: string;
  value?: unknown;
}

export type Author = 'user' | 'system' | 'agent' | 'policy-engine';

export interface Delta {
  delta_id: number | UUID;
  entity_id?: UUID;
  hash: SHA256;
  hash_prev: SHA256 | null;
  patch: JsonPatch[];
  author_type: Author;
  author_id: string;
  meta: Record<string, unknown>;
  created_at: Timestamp | string;
}

// === TENANT ===

export type TenantTier = 'FREE' | 'STARTER' | 'ENTERPRISE';
export type IsolationModel = 'SILOED' | 'POOLED';

export interface TenantQuotas {
  max_agents: number;
  max_actions_per_hour: number;
  max_entities: number;
  max_delta_log_size: number;
  max_webhook_count: number;
}

export const DEFAULT_QUOTAS: Record<TenantTier, TenantQuotas> = {
  FREE: {
    max_agents: 2,
    max_actions_per_hour: 100,
    max_entities: 500,
    max_delta_log_size: 5000,
    max_webhook_count: 2,
  },
  STARTER: {
    max_agents: 10,
    max_actions_per_hour: 1000,
    max_entities: 5000,
    max_delta_log_size: 50000,
    max_webhook_count: 10,
  },
  ENTERPRISE: {
    max_agents: 100,
    max_actions_per_hour: 10000,
    max_entities: 100000,
    max_delta_log_size: 500000,
    max_webhook_count: 100,
  },
};

export interface TenantRecord {
  tenant_id: UUID;
  name: string;
  tier: TenantTier;
  mode: Mode;
  quotas: TenantQuotas;
  api_key_hash: SHA256;
  db_name: string;
  enabled: boolean;
  isolation_model: IsolationModel;
  capabilities: string[];
  created_at: string;
  updated_at: string;
}

// === AGENT ===

export type AgentProvider = 'claude' | 'openai' | 'local' | 'custom';

export type AgentActionName =
  | 'create_task'
  | 'update_task'
  | 'complete_task'
  | 'delete_task'
  | 'query_state'
  | 'propose_delta'
  | 'route_decision'
  | 'request_approval'
  | 'get_policy_simulation'
  | 'register_webhook';

export interface AgentRecord {
  agent_id: UUID;
  name: string;
  provider: AgentProvider;
  version: string;
  capabilities: AgentActionName[];
  cost_center: string;
  enabled: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  last_active_at: string;
}

// === CANONICAL AGENT ACTION ===

export interface CanonicalAgentAction {
  action_id: UUID;
  tenant_id: UUID;
  agent_id: UUID;
  agent_version: string;
  action: AgentActionName;
  params: Record<string, unknown>;
  metadata: {
    provider: AgentProvider;
    model_id?: string;
    raw_tool_call?: unknown;
    tokens_used?: number;
    cost_usd?: number;
    latency_ms?: number;
  };
  timestamp: Timestamp;
  idempotency_key?: string;
}

// === TASK ===

export type AegisTaskStatus = 'OPEN' | 'IN_PROGRESS' | 'BLOCKED' | 'DONE' | 'ARCHIVED';
export type ApprovalStatus = 'NOT_REQUIRED' | 'PENDING' | 'APPROVED' | 'REJECTED';
export type Priority = 1 | 2 | 3 | 4 | 5;

// === POLICY ===

export type PolicyEffect = 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN';
export type PolicyOperator = 'eq' | 'neq' | 'in' | 'not_in' | 'gt' | 'lt' | 'gte' | 'lte' | 'exists';

export interface PolicyCondition {
  field: string;
  operator: PolicyOperator;
  value: unknown;
}

export interface PolicyRule {
  rule_id: UUID;
  name: string;
  description: string;
  priority: number;
  conditions: PolicyCondition[];
  effect: PolicyEffect;
  reason: string;
  enabled: boolean;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface PolicyEvaluationContext {
  tenant: { id: UUID; tier: TenantTier; mode: Mode };
  agent: { id: UUID; provider: AgentProvider; capabilities: AgentActionName[] };
  action: AgentActionName;
  params: Record<string, unknown>;
  mode: Mode;
}

export interface PolicyDecision {
  decision_id: UUID;
  tenant_id: UUID;
  agent_id: UUID;
  action: AgentActionName;
  effect: PolicyEffect;
  matched_rule_id: UUID | null;
  reason: string;
  context: {
    mode: Mode;
    tenant_tier: TenantTier;
    agent_provider: AgentProvider;
  };
  cached: boolean;
  evaluated_at: Timestamp;
  cache_ttl_ms: number;
}

// === APPROVAL ===

export type ApprovalWorkflowStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED';

// === WEBHOOK EVENTS ===

export type WebhookEventType =
  | 'action.completed'
  | 'action.denied'
  | 'approval.requested'
  | 'approval.decided'
  | 'task.created'
  | 'task.completed'
  | 'policy.violated'
  | 'tenant.mode_changed';

// === API RESPONSE TYPES ===

export interface ActionResponse {
  status: 'executed' | 'denied' | 'pending_approval';
  action_id: UUID;
  result?: {
    entity_id: UUID;
    delta_id: number | UUID;
    state: unknown;
  };
  policy_decision: {
    effect: PolicyEffect;
    matched_rule: string | null;
    reason: string;
    cached: boolean;
  };
  approval?: {
    approval_id: UUID;
    status: ApprovalWorkflowStatus;
    expires_at: Timestamp;
  };
  usage?: {
    actions_remaining_this_hour: number;
  };
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime_ms: number;
  version: string;
  components?: Record<string, { status: string; latency_ms?: number }>;
}
