/**
 * Aegis Enterprise Fabric — Metrics Routes
 * GET /api/v1/metrics/usage — Cost/usage per tenant
 * GET /metrics              — Prometheus metrics
 * GET /health               — Health check
 */

import { Router, Request, Response } from 'express';
import { UsageTracker } from '../../cost/usage-tracker.js';
import { metrics } from '../../observability/metrics.js';
import { getHealth } from '../../observability/health.js';
import { AegisStorage } from '../../storage/aegis-storage.js';
import { TenantRegistry } from '../../tenants/tenant-registry.js';

export function metricsRoutes(
  usageTracker: UsageTracker,
  storage: AegisStorage,
  tenantRegistry: TenantRegistry
): Router {
  const router = Router();

  router.get('/api/v1/metrics/usage', (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }

    const period = req.query.period as string | undefined;
    const agentId = req.query.agent_id as string | undefined;

    if (agentId) {
      const records = usageTracker.getUsageByAgent(req.tenant.id, agentId, period);
      res.json({ agent_id: agentId, records });
      return;
    }

    const records = usageTracker.getUsage(req.tenant.id, period);
    const totals = usageTracker.getTenantTotals(req.tenant.id);
    res.json({ tenant_id: req.tenant.id, totals, records });
  });

  router.get('/metrics', (_req: Request, res: Response) => {
    res.set('Content-Type', 'text/plain; charset=utf-8');
    res.send(metrics.toPrometheusText());
  });

  router.get('/health', (_req: Request, res: Response) => {
    const health = getHealth(storage, tenantRegistry);
    const statusCode = health.status === 'healthy' ? 200 : health.status === 'degraded' ? 200 : 503;
    res.status(statusCode).json(health);
  });

  return router;
}
