/**
 * Delta Kernel — Health Route
 */

import type { FastifyInstance } from 'fastify';
import type { PoolManager } from '../db/pool-manager.js';

export function healthRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  app.get('/health', async (_req, reply) => {
    const db = await poolManager.healthCheck();

    const status = db.connected ? 'healthy' : 'unhealthy';

    return reply.status(db.connected ? 200 : 503).send({
      status,
      uptime_ms: process.uptime() * 1000,
      version: '0.1.0',
      components: {
        postgres: {
          status: db.connected ? 'connected' : 'disconnected',
          latency_ms: db.latencyMs,
        },
      },
    });
  });
}
