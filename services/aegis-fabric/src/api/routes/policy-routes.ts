/**
 * Aegis Enterprise Fabric — Policy Routes
 * GET  /api/v1/policies          — List policies
 * POST /api/v1/policies          — Create/update policy rules
 * POST /api/v1/policies/simulate — Dry-run policy evaluation
 */

import { Router, Request, Response } from 'express';
import { PolicyStore } from '../../policies/policy-store.js';
import { PolicyEngine } from '../../policies/policy-engine.js';
import { AgentRegistry } from '../../agents/agent-registry.js';
import { TenantRegistry } from '../../tenants/tenant-registry.js';
import { PolicyEvaluationContext } from '../../core/types.js';
import { logger } from '../../observability/logger.js';
import { metrics } from '../../observability/metrics.js';

export function policyRoutes(
  policyStore: PolicyStore,
  policyEngine: PolicyEngine,
  agentRegistry: AgentRegistry,
  tenantRegistry: TenantRegistry
): Router {
  const router = Router();

  router.get('/api/v1/policies', (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }

    const rules = policyStore.getRules(req.tenant.id);
    const policy = policyStore.getPolicy(req.tenant.id);
    res.json({
      version: policy?.data.version || 0,
      rules: rules.map(r => ({
        rule_id: r.rule_id,
        name: r.name,
        priority: r.priority,
        conditions: r.conditions,
        effect: r.effect,
        reason: r.reason,
        enabled: r.enabled,
      })),
    });
  });

  router.post('/api/v1/policies', async (req: Request, res: Response) => {
    try {
      if (!req.tenant) {
        res.status(401).json({ error: 'Tenant authentication required' });
        return;
      }

      const { rules, rule } = req.body;

      // Bulk create
      if (rules && Array.isArray(rules)) {
        const result = await policyStore.createPolicy(req.tenant.id, rules);
        policyEngine.invalidateCache(req.tenant.id);
        logger.info('Policy created', { tenant_id: req.tenant.id, rule_count: rules.length });
        res.status(201).json({ policy_id: result.policyId, rules_count: rules.length });
        return;
      }

      // Single rule add
      if (rule) {
        const newRule = await policyStore.addRule(req.tenant.id, rule);
        policyEngine.invalidateCache(req.tenant.id);
        logger.info('Policy rule added', { tenant_id: req.tenant.id, rule_id: newRule.rule_id });
        res.status(201).json({ rule: newRule });
        return;
      }

      res.status(400).json({ error: 'Provide "rules" array or single "rule" object' });
    } catch (err) {
      logger.error('Failed to create policy', { error: String(err) });
      res.status(500).json({ error: 'Failed to create policy' });
    }
  });

  router.post('/api/v1/policies/simulate', (req: Request, res: Response) => {
    try {
      if (!req.tenant) {
        res.status(401).json({ error: 'Tenant authentication required' });
        return;
      }

      const { agent_id, action, params } = req.body;
      if (!agent_id || !action) {
        res.status(400).json({ error: 'agent_id and action are required' });
        return;
      }

      const agent = agentRegistry.getAgent(req.tenant.id, agent_id);
      if (!agent) {
        res.status(404).json({ error: 'Agent not found' });
        return;
      }

      const context: PolicyEvaluationContext = {
        tenant: { id: req.tenant.id, tier: req.tenant.data.tier, mode: req.tenant.data.mode },
        agent: { id: agent_id, provider: agent.state.provider, capabilities: agent.state.capabilities },
        action,
        params: params || {},
        mode: req.tenant.data.mode,
      };

      const simulation = policyEngine.simulate(context);
      metrics.increment('aegis_policy_evaluations_total', { effect: simulation.decision.effect });

      res.json({
        decision: {
          effect: simulation.decision.effect,
          reason: simulation.decision.reason,
          matched_rule_id: simulation.decision.matched_rule_id,
        },
        evaluated_rules: simulation.evaluated_rules.map(r => ({
          rule_id: r.rule.rule_id,
          name: r.rule.name,
          matched: r.matched,
          effect: r.rule.effect,
        })),
      });
    } catch (err) {
      logger.error('Policy simulation failed', { error: String(err) });
      res.status(500).json({ error: 'Policy simulation failed' });
    }
  });

  return router;
}
