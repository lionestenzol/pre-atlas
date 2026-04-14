/**
 * Aegis Enterprise Fabric — Tenant Routes
 * POST /api/v1/tenants — Create tenant (admin key)
 * GET  /api/v1/tenants — List tenants (admin key)
 */

import { Router, Request, Response } from 'express';
import { TenantRegistry } from '../../tenants/tenant-registry.js';
import { logger } from '../../observability/logger.js';

export function tenantRoutes(tenantRegistry: TenantRegistry): Router {
  const router = Router();

  router.post('/api/v1/tenants', async (req: Request, res: Response) => {
    try {
      const { name, tier, mode, isolation_model, quotas } = req.body;
      if (!name) {
        res.status(400).json({ error: 'name is required' });
        return;
      }

      const { tenant, apiKey } = await tenantRegistry.createTenant({
        name, tier, mode, isolation_model, quotas,
      });

      logger.info('Tenant created', { tenant_id: tenant.id, name });

      res.status(201).json({
        tenant_id: tenant.id,
        name: tenant.data.name,
        tier: tenant.data.tier,
        mode: tenant.data.mode,
        api_key: apiKey,
        quotas: tenant.data.quotas,
      });
    } catch (err) {
      logger.error('Failed to create tenant', { error: String(err) });
      res.status(500).json({ error: 'Failed to create tenant' });
    }
  });

  router.get('/api/v1/tenants', (req: Request, res: Response) => {
    const tenants = tenantRegistry.listTenants();
    res.json({
      tenants: tenants.map(t => ({
        tenant_id: t.id,
        name: t.data.name,
        tier: t.data.tier,
        mode: t.data.mode,
        enabled: t.data.enabled,
        quotas: t.data.quotas,
        created_at: t.data.created_at,
      })),
    });
  });

  return router;
}
