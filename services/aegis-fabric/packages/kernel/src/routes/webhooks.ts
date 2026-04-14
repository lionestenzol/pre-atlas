/**
 * Delta Kernel — Webhook Routes
 *
 * POST   /v1/webhooks     — register a webhook
 * GET    /v1/webhooks     — list webhooks
 * GET    /v1/webhooks/:id — get webhook
 * DELETE /v1/webhooks/:id — delete webhook
 */

import type { FastifyInstance } from 'fastify';
import type { WebhookEventType } from '@aegis/shared';
import { WebhookStore } from '../db/webhook-store.js';
import type { PoolManager } from '../db/pool-manager.js';

const webhookStore = new WebhookStore();

export function webhookRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // POST /v1/webhooks
  app.post('/v1/webhooks', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const body = req.body as {
      url: string;
      events: WebhookEventType[];
      secret: string;
    };

    if (!body.url || !body.events || !body.secret) {
      return reply.status(400).send({ error: 'url, events, and secret are required' });
    }

    const webhook = await webhookStore.create(pool, body);
    return reply.status(201).send(webhook);
  });

  // GET /v1/webhooks
  app.get('/v1/webhooks', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const webhooks = await webhookStore.getAll(pool);
    return reply.send({ webhooks, count: webhooks.length });
  });

  // GET /v1/webhooks/:id
  app.get('/v1/webhooks/:id', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const { id } = req.params as { id: string };
    const webhook = await webhookStore.getById(pool, id);

    if (!webhook) return reply.status(404).send({ error: 'Webhook not found' });
    return reply.send(webhook);
  });

  // DELETE /v1/webhooks/:id
  app.delete('/v1/webhooks/:id', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const { id } = req.params as { id: string };
    const deleted = await webhookStore.delete(pool, id);

    if (!deleted) return reply.status(404).send({ error: 'Webhook not found' });
    return reply.status(204).send();
  });
}
