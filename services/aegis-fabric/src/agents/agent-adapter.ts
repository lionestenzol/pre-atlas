/**
 * Aegis Enterprise Fabric — Agent Adapter
 *
 * Normalizes diverse LLM tool call formats into CanonicalAgentAction.
 * Supports: Claude (tool_use), OpenAI (function call), and custom/direct formats.
 */

import {
  UUID, CanonicalAgentAction, AgentActionName, AgentProvider,
} from '../core/types.js';
import { generateUUID, now } from '../core/delta.js';

const VALID_ACTIONS: Set<AgentActionName> = new Set([
  'create_task', 'update_task', 'complete_task', 'delete_task',
  'query_state', 'propose_delta', 'route_decision',
  'request_approval', 'get_policy_simulation', 'register_webhook',
]);

export interface AdapterResult {
  success: boolean;
  action?: CanonicalAgentAction;
  error?: string;
}

/**
 * Claude tool_use format:
 * { type: "tool_use", name: "create_task", input: { title: "...", priority: 3 } }
 */
function normalizeClaudeFormat(
  raw: Record<string, unknown>,
  tenantId: UUID,
  agentId: UUID,
  agentVersion: string
): AdapterResult {
  const name = raw.name as string;
  if (!name || !VALID_ACTIONS.has(name as AgentActionName)) {
    return { success: false, error: `Invalid Claude tool name: ${name}` };
  }

  const input = (raw.input || {}) as Record<string, unknown>;

  return {
    success: true,
    action: {
      action_id: generateUUID(),
      tenant_id: tenantId,
      agent_id: agentId,
      agent_version: agentVersion,
      action: name as AgentActionName,
      params: input,
      metadata: {
        provider: 'claude',
        model_id: (raw.model as string) || undefined,
        raw_tool_call: raw,
      },
      timestamp: now(),
    },
  };
}

/**
 * OpenAI function call format:
 * { function: { name: "create_task", arguments: "{ \"title\": \"...\" }" } }
 */
function normalizeOpenAIFormat(
  raw: Record<string, unknown>,
  tenantId: UUID,
  agentId: UUID,
  agentVersion: string
): AdapterResult {
  const fn = raw.function as Record<string, unknown> | undefined;
  if (!fn) {
    return { success: false, error: 'Missing function field in OpenAI format' };
  }

  const name = fn.name as string;
  if (!name || !VALID_ACTIONS.has(name as AgentActionName)) {
    return { success: false, error: `Invalid OpenAI function name: ${name}` };
  }

  let params: Record<string, unknown> = {};
  if (typeof fn.arguments === 'string') {
    try {
      params = JSON.parse(fn.arguments);
    } catch {
      return { success: false, error: 'Failed to parse OpenAI function arguments' };
    }
  } else if (typeof fn.arguments === 'object' && fn.arguments !== null) {
    params = fn.arguments as Record<string, unknown>;
  }

  return {
    success: true,
    action: {
      action_id: generateUUID(),
      tenant_id: tenantId,
      agent_id: agentId,
      agent_version: agentVersion,
      action: name as AgentActionName,
      params,
      metadata: {
        provider: 'openai',
        model_id: (raw.model as string) || undefined,
        raw_tool_call: raw,
      },
      timestamp: now(),
    },
  };
}

/**
 * Direct/custom format — already a CanonicalAgentAction or close to it.
 */
function normalizeDirectFormat(
  raw: Record<string, unknown>,
  tenantId: UUID,
  agentId: UUID,
  agentVersion: string,
  provider: AgentProvider
): AdapterResult {
  const action = raw.action as string;
  if (!action || !VALID_ACTIONS.has(action as AgentActionName)) {
    return { success: false, error: `Invalid action: ${action}` };
  }

  const params = (raw.params || {}) as Record<string, unknown>;
  const metadata = (raw.metadata || {}) as Record<string, unknown>;

  return {
    success: true,
    action: {
      action_id: (raw.action_id as string) || generateUUID(),
      tenant_id: tenantId,
      agent_id: agentId,
      agent_version: agentVersion,
      action: action as AgentActionName,
      params,
      metadata: {
        provider,
        model_id: metadata.model_id as string | undefined,
        tokens_used: metadata.tokens_used as number | undefined,
        cost_usd: metadata.cost_usd as number | undefined,
        latency_ms: metadata.latency_ms as number | undefined,
        raw_tool_call: raw,
      },
      timestamp: (raw.timestamp as number) || now(),
      idempotency_key: raw.idempotency_key as string | undefined,
    },
  };
}

/**
 * Main adapter: detects format and normalizes to CanonicalAgentAction.
 */
export function normalizeAgentAction(
  raw: Record<string, unknown>,
  tenantId: UUID,
  agentId: UUID,
  agentVersion: string,
  provider: AgentProvider
): AdapterResult {
  // Claude format detection
  if (raw.type === 'tool_use' && raw.name) {
    return normalizeClaudeFormat(raw, tenantId, agentId, agentVersion);
  }

  // OpenAI format detection
  if (raw.function && typeof raw.function === 'object') {
    return normalizeOpenAIFormat(raw, tenantId, agentId, agentVersion);
  }

  // Direct/custom format (has 'action' field)
  if (raw.action && typeof raw.action === 'string') {
    return normalizeDirectFormat(raw, tenantId, agentId, agentVersion, provider);
  }

  return { success: false, error: 'Unrecognized agent action format' };
}
