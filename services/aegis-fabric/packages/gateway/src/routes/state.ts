/**
 * Aegis Gateway — State Routes (proxy to kernel)
 *
 * GET /v1/state/query    — query entities
 * GET /v1/state/snapshot — get state at delta
 */

import type { FastifyInstance } from 'fastify';
import { getTenantFromRequest } from '../plugins/auth.js';
import { kernelRequest } from '../kernel-client.js';

export function stateRoutes(app: FastifyInstance): void {
  // GET /v1/state/query
  app.get('/v1/state/query', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const query = req.query as Record<string, string>;
    const res = await kernelRequest({
      method: 'GET',
      path: '/v1/state/query',
      tenantDb: tenant.db_name,
      query,
    });

    return reply.status(res.status).send(res.data);
  });

  // GET /v1/state/snapshot
  app.get('/v1/state/snapshot', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const query = req.query as Record<string, string>;
    const res = await kernelRequest({
      method: 'GET',
      path: '/v1/state/snapshot',
      tenantDb: tenant.db_name,
      query,
    });

    return reply.status(res.status).send(res.data);
  });
}
