/**
 * Aegis Gateway — Agent Adapter
 *
 * Normalizes agent action requests from Claude, OpenAI, or direct format
 * into a CanonicalAgentAction for the kernel.
 */

import { generateUUID, now } from '@aegis/shared';
import type { AgentActionName, AgentProvider, CanonicalAgentAction } from '@aegis/shared';

interface RawActionBody {
  agent_id: string;
  source?: AgentProvider;
  // Claude format
  type?: string;
  name?: string;
  input?: Record<string, unknown>;
  // OpenAI format
  function?: { name?: string; arguments?: string | Record<string, unknown> };
  // Direct format
  action?: string;
  params?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  idempotency_key?: string;
}

export function normalizeAgentAction(body: RawActionBody, tenantId: string): CanonicalAgentAction {
  const provider = detectProvider(body);
  let action: AgentActionName;
  let params: Record<string, unknown>;

  switch (provider) {
    case 'claude': {
      // Claude tool_use format: { type: "tool_use", name: "create_task", input: {...} }
      action = body.name as AgentActionName;
      params = body.input || {};
      break;
    }
    case 'openai': {
      // OpenAI function format: { function: { name: "create_task", arguments: "{...}" } }
      const fn = body.function!;
      action = fn.name as AgentActionName;
      params = typeof fn.arguments === 'string'
        ? JSON.parse(fn.arguments)
        : fn.arguments || {};
      break;
    }
    default: {
      // Direct format: { action: "create_task", params: {...} }
      action = (body.action || body.name) as AgentActionName;
      params = body.params || body.input || {};
    }
  }

  return {
    action_id: generateUUID(),
    tenant_id: tenantId,
    agent_id: body.agent_id,
    agent_version: '1.0.0',
    action,
    params,
    metadata: {
      provider,
      raw_tool_call: body,
      ...(body.metadata || {}),
    },
    timestamp: now(),
    idempotency_key: body.idempotency_key,
  };
}

function detectProvider(body: RawActionBody): AgentProvider {
  if (body.source) return body.source;
  if (body.type === 'tool_use' || (body.name && body.input)) return 'claude';
  if (body.function?.name) return 'openai';
  return 'custom';
}
