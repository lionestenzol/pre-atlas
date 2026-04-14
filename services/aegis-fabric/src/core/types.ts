/**
 * Aegis Enterprise Fabric — Type Definitions
 *
 * All entity types, enums, and interfaces for the AEF system.
 * Extends delta-kernel patterns with multi-tenancy, policy, and agent governance.
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
  delta_id: UUID;
  entity_id: UUID;
  tenant_id: UUID;
  timestamp: Timestamp;
  author: Author;
  patch: JsonPatch[];
  prev_hash: SHA256;
  new_hash: SHA256;
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

export interface TenantData {
  name: string;
  tier: TenantTier;
  mode: Mode;
  isolation_model: IsolationModel;
  quotas: TenantQuotas;
  api_key_hash: SHA256;
  capabilities: string[];
  enabled: boolean;
  created_at: Timestamp;
  updated_at: Timestamp;
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

export interface AgentData {
  tenant_id: UUID;
  name: string;
  provider: AgentProvider;
  version: string;
  capabilities: AgentActionName[];
  cost_center: string;
  enabled: boolean;
  metadata: Record<string, unknown>;
  created_at: Timestamp;
  last_active_at: Timestamp;
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

// === TASK (Enterprise Enhanced) ===

export type AegisTaskStatus = 'OPEN' | 'IN_PROGRESS' | 'BLOCKED' | 'DONE' | 'ARCHIVED';
export type ApprovalStatus = 'NOT_REQUIRED' | 'PENDING' | 'APPROVED' | 'REJECTED';
export type Priority = 1 | 2 | 3 | 4 | 5;

export interface AegisTaskData {
  tenant_id: UUID;
  title: string;
  description: string;
  status: AegisTaskStatus;
  priority: Priority;
  tags: string[];
  assignee: UUID | null;
  approval_required: boolean;
  approval_status: ApprovalStatus;
  due_at: Timestamp | null;
  linked_entities: UUID[];
  metadata: Record<string, unknown>;
  created_by: UUID;
  created_at: Timestamp;
  updated_at: Timestamp;
}

// === POLICY ===

export type PolicyEffect = 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN';
export type PolicyOperator = 'eq' | 'neq' | 'in' | 'not_in' | 'gt' | 'lt' | 'gte' | 'lte' | 'exists';

export interface PolicyCondition {
  field: string;   // dot-path: 'tenant.tier', 'agent.provider', 'action', 'mode'
  operator: PolicyOperator;
  value: unknown;
}

export interface PolicyRule {
  rule_id: UUID;
  name: string;
  description: string;
  priority: number;   // lower = higher priority
  conditions: PolicyCondition[];   // AND logic
  effect: PolicyEffect;
  reason: string;
  enabled: boolean;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface PolicyData {
  tenant_id: UUID;
  rules: PolicyRule[];
  version: number;
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

export interface ApprovalData {
  tenant_id: UUID;
  action_id: UUID;
  agent_id: UUID;
  action: AgentActionName;
  params: Record<string, unknown>;
  status: ApprovalWorkflowStatus;
  requested_at: Timestamp;
  decided_at: Timestamp | null;
  decided_by: string | null;
  reason: string | null;
  expires_at: Timestamp;
}

// === WEBHOOK ===

export type WebhookEventType =
  | 'action.completed'
  | 'action.denied'
  | 'approval.requested'
  | 'approval.decided'
  | 'task.created'
  | 'task.completed'
  | 'policy.violated'
  | 'tenant.mode_changed';

export interface WebhookData {
  tenant_id: UUID;
  url: string;
  events: WebhookEventType[];
  secret_hash: SHA256;
  enabled: boolean;
  retry_count: number;
  last_triggered_at: Timestamp | null;
  failure_count: number;
  created_at: Timestamp;
}

// === USAGE TRACKING ===

export interface UsageRecord {
  tenant_id: UUID;
  agent_id: UUID;
  period: string;   // 'YYYY-MM-DD' or 'YYYY-MM'
  actions_count: number;
  tokens_used: number;
  cost_usd: number;
  by_action: Partial<Record<AgentActionName, number>>;
  updated_at: Timestamp;
}

// === AUDIT ===

export interface AuditEntry {
  audit_id: UUID;
  tenant_id: UUID;
  agent_id: UUID;
  action: AgentActionName;
  effect: PolicyEffect;
  entity_ids_affected: UUID[];
  delta_id: UUID | null;
  timestamp: Timestamp;
  metadata: Record<string, unknown>;
}

// === ENTITY DATA MAP ===

export interface AegisEntityDataMap {
  aegis_tenant: TenantData;
  aegis_agent: AgentData;
  aegis_task: AegisTaskData;
  aegis_policy: PolicyData;
  aegis_approval: ApprovalData;
  aegis_webhook: WebhookData;
  aegis_usage_record: UsageRecord;
  aegis_audit_entry: AuditEntry;
}

// === SNAPSHOT ===

export interface Snapshot {
  snapshot_id: UUID;
  tenant_id: UUID;
  delta_count: number;
  last_delta_id: UUID;
  last_delta_hash: SHA256;
  entities: Array<{ entity: Entity; state: unknown }>;
  created_at: Timestamp;
}

// === API RESPONSE TYPES ===

export interface ActionResponse {
  status: 'executed' | 'denied' | 'pending_approval';
  action_id: UUID;
  result?: {
    entity_id: UUID;
    delta_id: UUID;
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
  tenants_loaded: number;
  storage_accessible: boolean;
}
