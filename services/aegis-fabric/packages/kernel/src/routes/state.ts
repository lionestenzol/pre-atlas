/**
 * Delta Kernel — State Routes
 *
 * GET /v1/state/query    — query entities by ID or type
 * GET /v1/state/snapshot — get state at specific delta (point-in-time)
 */

import type { FastifyInstance } from 'fastify';
import { stateQuerySchema } from '@aegis/shared';
import { EntityStore } from '../db/entity-store.js';
import { SnapshotStore } from '../db/snapshot-store.js';
import { DeltaStore } from '../db/delta-store.js';
import { StateMaterializer } from '../services/state-materializer.js';
import type { PoolManager } from '../db/pool-manager.js';

const entityStore = new EntityStore();
const snapshotStore = new SnapshotStore();
const deltaStore = new DeltaStore();
const materializer = new StateMaterializer();

export function stateRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  // GET /v1/state/query
  app.get('/v1/state/query', { schema: stateQuerySchema }, async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const query = req.query as {
      entity_id?: string;
      entity_type?: string;
      limit?: number;
    };

    // Query by entity_id
    if (query.entity_id) {
      const entity = await entityStore.getById(pool, query.entity_id);
      if (!entity) return reply.status(404).send({ error: 'Entity not found' });
      return reply.send({ entity });
    }

    // Query by entity_type
    if (query.entity_type) {
      const entities = await entityStore.getByType(pool, query.entity_type, {
        limit: query.limit,
      });
      return reply.send({ entities, count: entities.length });
    }

    // Get all entities
    const entities = await entityStore.getAll(pool);
    return reply.send({ entities, count: entities.length });
  });

  // GET /v1/state/snapshot
  app.get('/v1/state/snapshot', async (req, reply) => {
    const tenantDb = (req.headers['x-tenant-db'] as string) || '';
    if (!tenantDb) return reply.status(400).send({ error: 'Missing x-tenant-db header' });

    const pool = poolManager.getTenantPool(tenantDb);
    const query = req.query as { as_of_delta?: string };

    if (query.as_of_delta) {
      const deltaId = parseInt(query.as_of_delta, 10);

      // Reconstruct state at a point in time
      const state = await materializer.reconstructAtDelta(pool, deltaId);
      return reply.send({ as_of_delta: deltaId, state });
    }

    // Return latest snapshot
    const snapshot = await snapshotStore.getLatest(pool);
    if (!snapshot) {
      return reply.send({ snapshot: null, message: 'No snapshots exist yet' });
    }

    return reply.send({ snapshot });
  });
}
