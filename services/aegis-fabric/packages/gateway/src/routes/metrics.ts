/**
 * Aegis Gateway — Metrics & Health Routes
 *
 * GET /health         — gateway health (includes kernel check)
 * GET /metrics        — basic metrics
 * GET /v1/metrics/usage — proxy usage from kernel
 */

import type { FastifyInstance } from 'fastify';
import type Redis from 'ioredis';
import { kernelHealthCheck, kernelRequest } from '../kernel-client.js';
import { getTenantFromRequest } from '../plugins/auth.js';

export function metricsRoutes(app: FastifyInstance, redis: Redis): void {
  // GET /health
  app.get('/health', async (_req, reply) => {
    const kernel = await kernelHealthCheck();

    let redisOk = false;
    const redisStart = Date.now();
    try {
      await redis.ping();
      redisOk = true;
    } catch {
      // Redis unhealthy
    }
    const redisLatency = Date.now() - redisStart;

    const healthy = kernel.healthy && redisOk;

    return reply.status(healthy ? 200 : 503).send({
      status: healthy ? 'healthy' : 'degraded',
      uptime_ms: process.uptime() * 1000,
      version: '0.1.0',
      components: {
        kernel: {
          status: kernel.healthy ? 'connected' : 'disconnected',
          latency_ms: kernel.latencyMs,
        },
        redis: {
          status: redisOk ? 'connected' : 'disconnected',
          latency_ms: redisLatency,
        },
      },
    });
  });

  // GET /metrics — basic Prometheus-style metrics
  app.get('/metrics', async (_req, reply) => {
    reply.header('Content-Type', 'text/plain');
    return reply.send([
      `# HELP gateway_uptime_seconds Gateway uptime in seconds`,
      `# TYPE gateway_uptime_seconds gauge`,
      `gateway_uptime_seconds ${Math.floor(process.uptime())}`,
      `# HELP gateway_memory_rss_bytes Resident set size in bytes`,
      `# TYPE gateway_memory_rss_bytes gauge`,
      `gateway_memory_rss_bytes ${process.memoryUsage().rss}`,
    ].join('\n'));
  });

  // GET /v1/metrics/usage — proxy to kernel
  app.get('/v1/metrics/usage', async (req, reply) => {
    const tenant = getTenantFromRequest(req);
    if (!tenant) return reply.status(401).send({ error: 'Unauthorized' });

    const query = req.query as Record<string, string>;
    const res = await kernelRequest({
      method: 'GET',
      path: '/v1/usage',
      tenantDb: tenant.db_name,
      query,
    });

    return reply.status(res.status).send(res.data);
  });
}
