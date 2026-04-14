/**
 * Delta Kernel — Agent Routes
 *
 * POST /v1/agents     — register an agent
 * GET  /v1/agents     — list agents for tenant
 * GET  /v1/agents/:id — get agent by ID
 * PUT  /v1/agents/:id — update agent
 */

import type { FastifyInstance } from 'fastify';
import { agentRegisterSchema } from '@aegis/shared';
import type { AgentProvider, AgentActionName } from '@aegis/shared';
import { AgentStore } from '../db/agent-store.js';
import type { PoolManager } from '../db/pool-manager.js';

const agentStore = new AgentStore();

export function agentRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // POST /v1/agents
  app.post('/v1/agents', { schema: agentRegisterSchema }, async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const body = req.body as {
      name: string;
      provider: AgentProvider;
      version?: string;
      capabilities?: AgentActionName[];
      cost_center?: string;
      metadata?: Record<string, unknown>;
    };

    const agent = await agentStore.create(pool, body);
    return reply.status(201).send(agent);
  });

  // GET /v1/agents
  app.get('/v1/agents', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const agents = await agentStore.getAll(pool);
    return reply.send({ agents, count: agents.length });
  });

  // GET /v1/agents/:id
  app.get('/v1/agents/:id', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const { id } = req.params as { id: string };
    const agent = await agentStore.getById(pool, id);

    if (!agent) return reply.status(404).send({ error: 'Agent not found' });
    return reply.send(agent);
  });

  // PUT /v1/agents/:id
  app.put('/v1/agents/:id', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const { id } = req.params as { id: string };
    const body = req.body as Partial<{
      name: string;
      provider: AgentProvider;
      version: string;
      capabilities: AgentActionName[];
      cost_center: string;
      enabled: boolean;
      metadata: Record<string, unknown>;
    }>;

    const agent = await agentStore.update(pool, id, body);
    if (!agent) return reply.status(404).send({ error: 'Agent not found' });
    return reply.send(agent);
  });
}
