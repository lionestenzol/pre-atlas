/**
 * Delta Kernel — Usage Routes
 *
 * GET /v1/usage        — get usage records (by agent or all)
 * GET /v1/usage/totals — get aggregate totals
 */

import type { FastifyInstance } from 'fastify';
import { UsageStore } from '../db/usage-store.js';
import type { PoolManager } from '../db/pool-manager.js';

const usageStore = new UsageStore();

export function usageRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // GET /v1/usage
  app.get('/v1/usage', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const query = req.query as { agent_id?: string; period?: string };

    let records;
    if (query.agent_id) {
      records = await usageStore.getByAgent(pool, query.agent_id, query.period);
    } else {
      records = await usageStore.getAll(pool, query.period);
    }

    return reply.send({ records, count: records.length });
  });

  // GET /v1/usage/totals
  app.get('/v1/usage/totals', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const totals = await usageStore.getTotals(pool);
    return reply.send(totals);
  });
}
