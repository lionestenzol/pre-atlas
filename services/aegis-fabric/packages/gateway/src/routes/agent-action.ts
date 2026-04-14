/**
 * Aegis Gateway — Agent Action Route
 *
 * POST /v1/agent/action
 *
 * The primary pipeline:
 * 1. Normalize agent action (Claude/OpenAI/direct)
 * 2. Auth (already done by plugin)
 * 3. Rate limit check
 * 4. Idempotency check
 * 5. Policy pre-check (local policy engine)
 * 6. Forward to kernel delta/append
 * 7. Store idempotency response
 */

import type { FastifyInstance } from 'fastify';
import type Redis from 'ioredis';
import { agentActionSchema } from '@aegis/shared';
import { PolicyEngine, DecisionCache } from '@aegis/shared';
import type { PolicyRule, UUID, PolicyEvaluationContext } from '@aegis/shared';
import { normalizeAgentAction } from '../adapters/agent-adapter.js';
import { getTenantFromRequest } from '../plugins/auth.js';
import { checkRateLimit } from '../plugins/rate-limit.js';
import { checkIdempotency, storeIdempotencyResponse } from '../plugins/idempotency.js';
import { kernelRequest } from '../kernel-client.js';

export function agentActionRoutes(app: FastifyInstance, redis: Redis): void {
  // Policy engine with kernel-backed rule provider
  const decisionCache = new DecisionCache(60_000);
  const policyEngine = new PolicyEngine(
    {
      getRules(tenantId: UUID): PolicyRule[] {
        // Synchronous — use cached rules. Rules are refreshed asynchronously.
        const cached = ruleCache.get(tenantId);
        return cached || [];
      },
    },
    decisionCache
  );

  // Local rule cache (refreshed on policy changes)
  const ruleCache = new Map<string, PolicyRule[]>();

  async function refreshRules(tenantId: string, tenantDb: string): Promise<void> {
    const res = await kernelRequest<{ rules: PolicyRule[] }>({
      method: 'GET',
      path: '/v1/policies/rules',
      tenantDb,
    });
    if (res.ok) {
      ruleCache.set(tenantId, res.data.rules || []);
    }
  }

  // POST /v1/agent/action
  app.post('/v1/agent/action', { schema: agentActionSchema }, async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    // 1. Normalize the action
    const body = req.body as unknown as Parameters<typeof normalizeAgentAction>[0];
    const canonical = normalizeAgentAction(body, tenant.tenant_id);

    // 2. Rate limit check
    const rateResult = await checkRateLimit(redis, tenant.tenant_id, tenant.quotas.max_actions_per_hour);
    if (!rateResult.allowed) {
      return reply.status(429).send({
        error: 'Rate limit exceeded',
        retry_after_ms: rateResult.retryAfterMs,
        limit: rateResult.limit,
        remaining: 0,
      });
    }

    // 3. Idempotency check
    if (canonical.idempotency_key) {
      const idemResult = await checkIdempotency(redis, tenant.tenant_id, canonical.idempotency_key);
      if (idemResult.cached) {
        return reply.send(idemResult.response);
      }
    }

    // 4. Policy pre-check
    // Ensure rules are loaded
    if (!ruleCache.has(tenant.tenant_id)) {
      await refreshRules(tenant.tenant_id, tenant.db_name);
    }

    const policyContext: PolicyEvaluationContext = {
      tenant: { id: tenant.tenant_id, tier: tenant.tier, mode: tenant.mode },
      agent: {
        id: canonical.agent_id,
        provider: canonical.metadata.provider,
        capabilities: [],
      },
      action: canonical.action,
      params: canonical.params,
      mode: tenant.mode,
    };

    const decision = policyEngine.evaluate(policyContext);

    if (decision.effect === 'DENY') {
      const response = {
        status: 'denied',
        action_id: canonical.action_id,
        policy_decision: {
          effect: decision.effect,
          matched_rule: decision.matched_rule_id,
          reason: decision.reason,
          cached: decision.cached,
        },
      };

      if (canonical.idempotency_key) {
        await storeIdempotencyResponse(redis, tenant.tenant_id, canonical.idempotency_key, response);
      }

      return reply.status(403).send(response);
    }

    if (decision.effect === 'REQUIRE_HUMAN') {
      // Create an approval request via kernel
      const approvalRes = await kernelRequest({
        method: 'POST',
        path: '/v1/approvals',
        tenantDb: tenant.db_name,
        body: {
          action_id: canonical.action_id,
          agent_id: canonical.agent_id,
          action: canonical.action,
          params: canonical.params,
        },
      });

      const response = {
        status: 'pending_approval',
        action_id: canonical.action_id,
        policy_decision: {
          effect: decision.effect,
          matched_rule: decision.matched_rule_id,
          reason: decision.reason,
          cached: decision.cached,
        },
        approval: approvalRes.data,
      };

      return reply.status(202).send(response);
    }

    // 5. Forward to kernel delta/append
    const deltaRes = await kernelRequest<Record<string, unknown>>({
      method: 'POST',
      path: '/v1/delta/append',
      tenantDb: tenant.db_name,
      body: {
        author: {
          type: 'agent',
          id: canonical.agent_id,
          source: canonical.metadata.provider,
        },
        patch: actionToPatch(canonical.action, canonical.params),
        entity_id: canonical.params.entity_id as string | undefined,
        meta: {
          requestId: canonical.action_id,
          idempotencyKey: canonical.idempotency_key,
          reason: `Agent action: ${canonical.action}`,
        },
      },
    });

    if (!deltaRes.ok) {
      return reply.status(deltaRes.status).send(deltaRes.data);
    }

    const response = {
      status: 'executed',
      action_id: canonical.action_id,
      result: deltaRes.data,
      policy_decision: {
        effect: decision.effect,
        matched_rule: decision.matched_rule_id,
        reason: decision.reason,
        cached: decision.cached,
      },
      usage: {
        actions_remaining_this_hour: rateResult.remaining,
      },
    };

    // 6. Store idempotency response
    if (canonical.idempotency_key) {
      await storeIdempotencyResponse(redis, tenant.tenant_id, canonical.idempotency_key, response);
    }

    return reply.status(201).send(response);
  });
}

/**
 * Convert an agent action into JSON Patch operations.
 */
function actionToPatch(action: string, params: Record<string, unknown>): Array<{ op: string; path: string; value?: unknown }> {
  switch (action) {
    case 'create_task':
      return [
        { op: 'add', path: '/title', value: params.title },
        { op: 'add', path: '/description', value: params.description || '' },
        { op: 'add', path: '/status', value: 'OPEN' },
        { op: 'add', path: '/priority', value: params.priority || 3 },
        { op: 'add', path: '/created_at', value: Date.now() },
      ];
    case 'update_task':
      return Object.entries(params)
        .filter(([key]) => key !== 'entity_id')
        .map(([key, value]) => ({ op: 'replace' as const, path: `/${key}`, value }));
    case 'complete_task':
      return [
        { op: 'replace', path: '/status', value: 'DONE' },
        { op: 'replace', path: '/completed_at', value: Date.now() },
      ];
    case 'delete_task':
      return [
        { op: 'replace', path: '/is_archived', value: true },
        { op: 'replace', path: '/archived_at', value: Date.now() },
      ];
    default:
      // Generic: wrap all params as add operations
      return Object.entries(params).map(([key, value]) => ({
        op: 'add',
        path: `/${key}`,
        value,
      }));
  }
}
