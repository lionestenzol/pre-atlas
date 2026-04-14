/**
 * Aegis Gateway — Webhook Routes (proxy to kernel)
 *
 * POST   /v1/webhooks     — register webhook
 * GET    /v1/webhooks     — list webhooks
 * DELETE /v1/webhooks/:id — remove webhook
 */

import type { FastifyInstance } from 'fastify';
import { getTenantFromRequest } from '../plugins/auth.js';
import { kernelRequest } from '../kernel-client.js';

export function webhookRoutes(app: FastifyInstance): void {
  app.post('/v1/webhooks', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const res = await kernelRequest({
      method: 'POST',
      path: '/v1/webhooks',
      tenantDb: tenant.db_name,
      body: req.body,
    });

    return reply.status(res.status).send(res.data);
  });

  app.get('/v1/webhooks', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const res = await kernelRequest({
      method: 'GET',
      path: '/v1/webhooks',
      tenantDb: tenant.db_name,
    });

    return reply.status(res.status).send(res.data);
  });

  app.delete('/v1/webhooks/:id', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const { id } = req.params as { id: string };
    const res = await kernelRequest({
      method: 'DELETE',
      path: `/v1/webhooks/${id}`,
      tenantDb: tenant.db_name,
    });

    return reply.status(res.status).send(res.data);
  });
}
