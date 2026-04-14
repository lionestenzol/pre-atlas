/**
 * Delta Kernel — Delta Routes
 *
 * POST /v1/delta/append — append a validated delta to the hash chain
 * GET  /v1/delta/verify — verify hash chain integrity
 * GET  /v1/delta/latest — get latest delta (chain head)
 * GET  /v1/delta/log    — get delta log entries
 */

import type { FastifyInstance } from 'fastify';
import { deltaAppendSchema } from '@aegis/shared';
import type { JsonPatch } from '@aegis/shared';
import { DeltaStore } from '../db/delta-store.js';
import { EntityStore } from '../db/entity-store.js';
import { AuditStore } from '../db/audit-store.js';
import type { PoolManager } from '../db/pool-manager.js';

const deltaStore = new DeltaStore();
const entityStore = new EntityStore();
const auditStore = new AuditStore();

export function deltaRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // POST /v1/delta/append
  app.post('/v1/delta/append', { schema: deltaAppendSchema }, async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const body = req.body as {
      author: { type: string; id: string; source?: string };
      patch: JsonPatch[];
      entity_id?: string;
      meta?: { requestId?: string; idempotencyKey?: string; reason?: string };
      hash_prev?: string;
    };

    try {
      let result;

      // If hash_prev is provided, use optimistic concurrency control
      if (body.hash_prev !== undefined) {
        result = await deltaStore.appendWithHashCheck(pool, {
          authorType: body.author.type,
          authorId: body.author.id,
          patch: body.patch,
          entityId: body.entity_id,
          meta: body.meta || {},
        }, body.hash_prev);

        if (!result) {
          return reply.status(409).send({
            error: 'Hash chain conflict',
            message: 'The provided hash_prev does not match the current chain head. Fetch the latest delta and retry.',
          });
        }
      } else {
        result = await deltaStore.append(pool, {
          authorType: body.author.type,
          authorId: body.author.id,
          patch: body.patch,
          entityId: body.entity_id,
          meta: body.meta || {},
        });
      }

      // If entity_id provided, update the entity state
      let entity = null;
      if (body.entity_id) {
        const existing = await entityStore.getById(pool, body.entity_id);
        if (existing) {
          entity = await entityStore.update(pool, body.entity_id, body.patch);
        }
      }

      // Audit the delta append
      await auditStore.append(pool, {
        agentId: body.author.id,
        action: 'propose_delta' as const,
        effect: 'ALLOW',
        entityIds: body.entity_id ? [body.entity_id] : [],
        deltaId: result.deltaId,
        metadata: { source: body.author.source || body.author.type },
      });

      return reply.status(201).send({
        delta_id: result.deltaId,
        hash: result.hash,
        hash_prev: result.hashPrev,
        timestamp: result.timestampMs,
        entity: entity ? { entity_id: entity.entity_id, version: entity.version, current_hash: entity.current_hash } : null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      return reply.status(500).send({ error: 'Delta append failed', message });
    }
  });

  // GET /v1/delta/verify
  app.get('/v1/delta/verify', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const result = await deltaStore.verifyChain(pool);
    const count = await deltaStore.getCount(pool);

    return reply.send({
      ...result,
      total_deltas: count,
      verified_at: new Date().toISOString(),
    });
  });

  // GET /v1/delta/latest
  app.get('/v1/delta/latest', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const latest = await deltaStore.getLatest(pool);

    if (!latest) return reply.status(404).send({ error: 'No deltas found' });
    return reply.send(latest);
  });

  // GET /v1/delta/log
  app.get('/v1/delta/log', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const query = req.query as { entity_id?: string; after?: string; limit?: string };

    const deltas = await deltaStore.getDeltas(pool, {
      entityId: query.entity_id,
      afterDeltaId: query.after ? parseInt(query.after, 10) : undefined,
      limit: query.limit ? parseInt(query.limit, 10) : 100,
    });

    return reply.send({ deltas, count: deltas.length });
  });
}
