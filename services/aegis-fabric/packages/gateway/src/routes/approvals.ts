/**
 * Aegis Gateway — Approval Routes (proxy to kernel)
 *
 * GET  /v1/approvals     — list pending approvals
 * GET  /v1/approvals/:id — get approval by ID
 * POST /v1/approvals/:id — approve/reject
 */

import type { FastifyInstance } from 'fastify';
import { getTenantFromRequest } from '../plugins/auth.js';
import { kernelRequest } from '../kernel-client.js';

export function approvalRoutes(app: FastifyInstance): void {
  // GET /v1/approvals
  app.get('/v1/approvals', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const query = req.query as { status?: string };
    const res = await kernelRequest({
      method: 'GET',
      path: '/v1/approvals',
      tenantDb: tenant.db_name,
      query: query.status ? { status: query.status } : undefined,
    });

    return reply.status(res.status).send(res.data);
  });

  // GET /v1/approvals/:id
  app.get('/v1/approvals/:id', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const { id } = req.params as { id: string };
    const res = await kernelRequest({
      method: 'GET',
      path: `/v1/approvals/${id}`,
      tenantDb: tenant.db_name,
    });

    return reply.status(res.status).send(res.data);
  });

  // POST /v1/approvals/:id
  app.post('/v1/approvals/:id', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const { id } = req.params as { id: string };
    const res = await kernelRequest({
      method: 'POST',
      path: `/v1/approvals/${id}`,
      tenantDb: tenant.db_name,
      body: req.body,
    });

    return reply.status(res.status).send(res.data);
  });
}
