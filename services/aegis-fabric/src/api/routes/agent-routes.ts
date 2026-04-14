/**
 * Aegis Enterprise Fabric — Agent Routes
 * POST /api/v1/agents       — Register agent
 * GET  /api/v1/agents       — List agents
 * POST /api/v1/agent/action — Submit agent action (primary endpoint)
 */

import { Router, Request, Response } from 'express';
import { AgentRegistry } from '../../agents/agent-registry.js';
import { ActionProcessor } from '../../agents/action-processor.js';
import { normalizeAgentAction } from '../../agents/agent-adapter.js';
import { RateLimiter } from '../../gateway/rate-limiter.js';
import { AuditLog } from '../../events/audit-log.js';
import { metrics } from '../../observability/metrics.js';
import { logger } from '../../observability/logger.js';

export function agentRoutes(
  agentRegistry: AgentRegistry,
  actionProcessor: ActionProcessor,
  rateLimiter: RateLimiter,
  auditLog: AuditLog
): Router {
  const router = Router();

  router.post('/api/v1/agents', async (req: Request, res: Response) => {
    try {
      if (!req.tenant) {
        res.status(401).json({ error: 'Tenant authentication required' });
        return;
      }

      const { name, provider, version, capabilities, cost_center, metadata } = req.body;
      if (!name || !provider) {
        res.status(400).json({ error: 'name and provider are required' });
        return;
      }

      const { agentId, entity } = await agentRegistry.registerAgent(req.tenant.id, {
        name, provider, version, capabilities, cost_center, metadata,
      });

      logger.info('Agent registered', { tenant_id: req.tenant.id, agent_id: agentId, name });
      metrics.incrementGauge('aegis_active_agents');

      res.status(201).json({
        agent_id: agentId,
        name,
        provider,
        capabilities: entity ? capabilities : undefined,
      });
    } catch (err) {
      logger.error('Failed to register agent', { error: String(err) });
      res.status(400).json({ error: String(err) });
    }
  });

  router.get('/api/v1/agents', (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }

    const agents = agentRegistry.listAgents(req.tenant.id);
    res.json({
      agents: agents.map(a => ({
        agent_id: a.entity.entity_id,
        name: a.state.name,
        provider: a.state.provider,
        version: a.state.version,
        capabilities: a.state.capabilities,
        enabled: a.state.enabled,
        last_active_at: a.state.last_active_at,
      })),
    });
  });

  router.post('/api/v1/agent/action', async (req: Request, res: Response) => {
    const start = Date.now();
    try {
      if (!req.tenant) {
        res.status(401).json({ error: 'Tenant authentication required' });
        return;
      }

      const agentId = req.body.agent_id as string;
      if (!agentId) {
        res.status(400).json({ error: 'agent_id is required' });
        return;
      }

      // Get agent for adapter
      const agent = agentRegistry.getAgent(req.tenant.id, agentId);
      if (!agent) {
        res.status(404).json({ error: 'Agent not found' });
        return;
      }

      // Normalize the action
      const adapted = normalizeAgentAction(
        req.body,
        req.tenant.id,
        agentId,
        agent.state.version,
        agent.state.provider
      );

      if (!adapted.success || !adapted.action) {
        res.status(400).json({ error: adapted.error });
        return;
      }

      // Process the action
      const result = await actionProcessor.process(adapted.action);

      // Metrics
      const duration = (Date.now() - start) / 1000;
      metrics.increment('aegis_actions_total', {
        tenant: req.tenant.id,
        agent: agentId,
        action: adapted.action.action,
        effect: result.policy_decision.effect,
      });
      metrics.observe('aegis_action_duration_seconds', {
        tenant: req.tenant.id,
        action: adapted.action.action,
      }, duration);

      // Audit
      auditLog.logAction({
        tenant_id: req.tenant.id,
        agent_id: agentId,
        action: adapted.action.action,
        effect: result.policy_decision.effect as any,
        entity_ids: result.result?.entity_id ? [result.result.entity_id] : [],
        delta_id: result.result?.delta_id || null,
      });

      // Add rate limit info
      const remaining = rateLimiter.getRemaining(req.tenant.id, agentId);
      if (remaining >= 0) {
        result.usage = { actions_remaining_this_hour: remaining };
      }

      const statusCode = result.status === 'denied' ? 403 : result.status === 'pending_approval' ? 202 : 200;
      res.status(statusCode).json(result);
    } catch (err) {
      logger.error('Action processing failed', { error: String(err) });
      res.status(500).json({ error: 'Action processing failed', detail: String(err) });
    }
  });

  // Audit log query
  router.get('/api/v1/audit', (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }
    const limit = req.query.limit ? Number(req.query.limit) : 20;
    const entries = auditLog.getEntries(req.tenant.id, limit);
    res.json({ entries });
  });

  return router;
}
