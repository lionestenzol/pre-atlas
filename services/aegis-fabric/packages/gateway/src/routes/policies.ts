/**
 * Aegis Gateway — Policy Routes (proxy to kernel + local simulate)
 *
 * GET  /v1/policies          — proxied to kernel
 * POST /v1/policies          — proxied to kernel
 * POST /v1/policies/simulate — local policy engine dry-run
 */

import type { FastifyInstance } from 'fastify';
import { PolicyEngine, DecisionCache } from '@aegis/shared';
import type { PolicyRule, UUID, PolicyEvaluationContext } from '@aegis/shared';
import { getTenantFromRequest } from '../plugins/auth.js';
import { kernelRequest } from '../kernel-client.js';

export function policyRoutes(app: FastifyInstance): void {
  // GET /v1/policies
  app.get('/v1/policies', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const res = await kernelRequest({
      method: 'GET',
      path: '/v1/policies',
      tenantDb: tenant.db_name,
    });

    return reply.status(res.status).send(res.data);
  });

  // POST /v1/policies
  app.post('/v1/policies', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const res = await kernelRequest({
      method: 'POST',
      path: '/v1/policies',
      tenantDb: tenant.db_name,
      body: req.body,
    });

    return reply.status(res.status).send(res.data);
  });

  // POST /v1/policies/simulate — local dry-run using shared policy engine
  app.post('/v1/policies/simulate', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const body = req.body as PolicyEvaluationContext;

    // Fetch current rules from kernel
    const rulesRes = await kernelRequest<{ rules: PolicyRule[] }>({
      method: 'GET',
      path: '/v1/policies/rules',
      tenantDb: tenant.db_name,
    });

    if (!rulesRes.ok) {
      return reply.status(502).send({ error: 'Failed to fetch policy rules from kernel' });
    }

    const rules = rulesRes.data.rules || [];

    // Create a temporary policy engine for simulation (no caching)
    const engine = new PolicyEngine({
      getRules(_tenantId: UUID): PolicyRule[] {
        return rules;
      },
    }, new DecisionCache(0));

    const result = engine.simulate(body);

    return reply.send(result);
  });
}
