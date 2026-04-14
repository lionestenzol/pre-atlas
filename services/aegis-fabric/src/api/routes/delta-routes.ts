/**
 * Aegis Enterprise Fabric — Delta Routes
 * GET /api/v1/deltas        — List deltas (optional entity_id filter)
 * GET /api/v1/deltas/verify — Verify hash chain integrity
 */

import { Router, Request, Response } from 'express';
import { AegisStorage } from '../../storage/aegis-storage.js';
import { verifyHashChain } from '../../core/delta.js';

export function deltaRoutes(storage: AegisStorage): Router {
  const router = Router();

  router.get('/api/v1/deltas/verify', async (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }

    const deltas = storage.loadDeltas(req.tenant.id);

    // Group deltas by entity_id — each entity has its own independent hash chain
    const byEntity = new Map<string, typeof deltas>();
    for (const d of deltas) {
      const arr = byEntity.get(d.entity_id) || [];
      arr.push(d);
      byEntity.set(d.entity_id, arr);
    }

    // Verify each entity's chain independently
    const entityResults: Array<{ entity_id: string; valid: boolean; delta_count: number }> = [];
    let allValid = true;

    for (const [entityId, entityDeltas] of byEntity) {
      const valid = await verifyHashChain(entityDeltas);
      entityResults.push({ entity_id: entityId, valid, delta_count: entityDeltas.length });
      if (!valid) allValid = false;
    }

    res.json({
      valid: allValid,
      delta_count: deltas.length,
      entity_count: byEntity.size,
      entities: entityResults,
      verified_at: Date.now(),
    });
  });

  router.get('/api/v1/deltas', (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }

    const entityId = req.query.entity_id as string | undefined;
    const deltas = entityId
      ? storage.loadDeltasForEntity(req.tenant.id, entityId)
      : storage.loadDeltas(req.tenant.id);

    res.json({
      count: deltas.length,
      deltas: deltas.map(d => ({
        delta_id: d.delta_id,
        entity_id: d.entity_id,
        timestamp: d.timestamp,
        author: d.author,
        patch: d.patch,
        prev_hash: d.prev_hash,
        new_hash: d.new_hash,
      })),
    });
  });

  return router;
}
