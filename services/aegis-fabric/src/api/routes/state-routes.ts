/**
 * Aegis Enterprise Fabric — State Routes
 * GET /api/v1/state/query — Query state with tenant isolation and optional point-in-time
 */

import { Router, Request, Response } from 'express';
import { AegisStorage } from '../../storage/aegis-storage.js';
import { SnapshotManager } from '../../storage/snapshot-manager.js';

export function stateRoutes(storage: AegisStorage, snapshotManager: SnapshotManager): Router {
  const router = Router();

  router.get('/api/v1/state/query', (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }

    const entityId = req.query.entity_id as string;
    const entityType = req.query.entity_type as string;
    const pointInTime = req.query.as_of ? Number(req.query.as_of) : undefined;

    // Point-in-time query
    if (pointInTime) {
      if (entityId) {
        const state = snapshotManager.queryEntityAtTime(req.tenant.id, entityId, pointInTime);
        res.json({ entity_id: entityId, as_of: pointInTime, state });
        return;
      }

      const stateMap = snapshotManager.rebuildState(req.tenant.id, pointInTime);
      const entities = Array.from(stateMap.entries()).map(([id, { entity, state }]) => ({
        entity_id: id,
        entity_type: entity.entity_type,
        state,
      }));
      res.json({ as_of: pointInTime, entities });
      return;
    }

    // Current state query
    if (entityId) {
      const result = storage.loadEntity(req.tenant.id, entityId);
      if (!result) {
        res.status(404).json({ error: 'Entity not found' });
        return;
      }
      res.json({
        entity_id: entityId,
        entity_type: result.entity.entity_type,
        version: result.entity.current_version,
        hash: result.entity.current_hash,
        state: result.state,
      });
      return;
    }

    if (entityType) {
      const results = storage.loadEntitiesByType(req.tenant.id, entityType as any);
      res.json({
        entity_type: entityType,
        count: results.length,
        entities: results.map(r => ({
          entity_id: r.entity.entity_id,
          version: r.entity.current_version,
          state: r.state,
        })),
      });
      return;
    }

    // Default: return stats
    const stats = storage.getStats(req.tenant.id);
    res.json({ tenant_id: req.tenant.id, stats });
  });

  return router;
}
