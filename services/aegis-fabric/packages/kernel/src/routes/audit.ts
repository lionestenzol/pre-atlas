/**
 * Delta Kernel — Audit Routes
 *
 * GET /v1/audit — query audit log entries
 */

import type { FastifyInstance } from 'fastify';
import { AuditStore } from '../db/audit-store.js';
import type { PoolManager } from '../db/pool-manager.js';

const auditStore = new AuditStore();

export function auditRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // GET /v1/audit
  app.get('/v1/audit', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const query = req.query as { agent_id?: string; action?: string; limit?: string };
    const limit = query.limit ? parseInt(query.limit, 10) : 50;

    let entries;
    if (query.agent_id) {
      entries = await auditStore.getByAgent(pool, query.agent_id, limit);
    } else if (query.action) {
      entries = await auditStore.getByAction(pool, query.action, limit);
    } else {
      entries = await auditStore.getRecent(pool, limit);
    }

    return reply.send({ entries, count: entries.length });
  });
}
