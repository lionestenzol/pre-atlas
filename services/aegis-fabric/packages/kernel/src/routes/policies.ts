/**
 * Delta Kernel — Policy Routes
 *
 * POST /v1/policies — create/replace policy rules
 * GET  /v1/policies — get current policy and rules
 */

import type { FastifyInstance } from 'fastify';
import { policyCreateSchema } from '@aegis/shared';
import type { PolicyRule } from '@aegis/shared';
import { PolicyStore } from '../db/policy-store.js';
import type { PoolManager } from '../db/pool-manager.js';

const policyStore = new PolicyStore();

export function policyRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // POST /v1/policies
  app.post('/v1/policies', { schema: policyCreateSchema }, async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const body = req.body as {
      rules?: Partial<PolicyRule>[];
      rule?: Partial<PolicyRule>;
    };

    // Bulk replace with multiple rules
    if (body.rules) {
      const policy = await policyStore.createPolicy(pool, body.rules);
      return reply.status(201).send(policy);
    }

    // Add a single rule
    if (body.rule) {
      const rule = await policyStore.addRule(pool, body.rule);
      return reply.status(201).send(rule);
    }

    return reply.status(400).send({ error: 'Provide either "rules" array or "rule" object' });
  });

  // GET /v1/policies
  app.get('/v1/policies', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const policy = await policyStore.getPolicy(pool);

    if (!policy) {
      return reply.send({ policy: null, rules: [] });
    }

    return reply.send({
      policy: {
        policy_id: policy.policy_id,
        version: policy.version,
        created_at: policy.created_at,
        updated_at: policy.updated_at,
      },
      rules: policy.rules,
    });
  });

  // GET /v1/policies/rules — get sorted enabled rules (for Gateway policy engine)
  app.get('/v1/policies/rules', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const rules = await policyStore.getRules(pool);

    return reply.send({ rules, count: rules.length });
  });
}
