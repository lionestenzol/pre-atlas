/**
 * Delta Kernel — Approval Routes
 *
 * GET  /v1/approvals     — list pending approvals
 * GET  /v1/approvals/:id — get approval by ID
 * POST /v1/approvals/:id — approve or reject
 */

import type { FastifyInstance } from 'fastify';
import { approvalDecideSchema } from '@aegis/shared';
import { ApprovalStore } from '../db/approval-store.js';
import { AuditStore } from '../db/audit-store.js';
import type { PoolManager } from '../db/pool-manager.js';

const approvalStore = new ApprovalStore();
const auditStore = new AuditStore();

export function approvalRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // GET /v1/approvals
  app.get('/v1/approvals', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const query = req.query as { status?: string };

    let approvals;
    if (query.status === 'PENDING') {
      approvals = await approvalStore.getPending(pool);
    } else {
      // getPending returns all pending; for all statuses, query directly
      approvals = await approvalStore.getPending(pool);
    }

    return reply.send({ approvals, count: approvals.length });
  });

  // GET /v1/approvals/:id
  app.get('/v1/approvals/:id', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const { id } = req.params as { id: string };
    const approval = await approvalStore.getById(pool, id);

    if (!approval) return reply.status(404).send({ error: 'Approval not found' });
    return reply.send(approval);
  });

  // POST /v1/approvals/:id
  app.post('/v1/approvals/:id', { schema: approvalDecideSchema }, async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const { id } = req.params as { id: string };
    const body = req.body as {
      decision: 'APPROVED' | 'REJECTED';
      decided_by?: string;
      reason?: string;
    };

    const result = await approvalStore.decide(
      pool, id, body.decision, body.decided_by || 'system', body.reason
    );

    if (!result) {
      return reply.status(404).send({ error: 'Approval not found or already decided' });
    }

    // Audit the decision
    await auditStore.append(pool, {
      agentId: result.agent_id,
      action: 'request_approval' as const,
      effect: body.decision === 'APPROVED' ? 'ALLOW' : 'DENY',
      metadata: { approval_id: id, decision: body.decision, decided_by: body.decided_by },
    });

    return reply.send(result);
  });
}
