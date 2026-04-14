/**
 * Aegis Gateway — Fastify Entry Point
 *
 * Stateless service backed by Redis (rate limiting, idempotency, caching).
 * Proxies authenticated + rate-limited requests to the Kernel.
 * Port: 3010
 */

import Fastify from 'fastify';
import cors from '@fastify/cors';
import fastifyStatic from '@fastify/static';
import Redis from 'ioredis';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { authPlugin } from './plugins/auth.js';
import { agentActionRoutes } from './routes/agent-action.js';
import { policyRoutes } from './routes/policies.js';
import { approvalRoutes } from './routes/approvals.js';
import { webhookRoutes } from './routes/webhooks.js';
import { stateRoutes } from './routes/state.js';
import { metricsRoutes } from './routes/metrics.js';

const PORT = Number(process.env.GATEWAY_PORT) || 3010;
const HOST = process.env.GATEWAY_HOST || '0.0.0.0';
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';

async function main(): Promise<void> {
  const app = Fastify({
    logger: {
      level: process.env.LOG_LEVEL || 'info',
    },
  });

  // CORS
  await app.register(cors, { origin: true });

  // Redis client
  const redis = new Redis(REDIS_URL);

  redis.on('error', (err) => {
    app.log.error({ err }, 'Redis connection error');
  });

  redis.on('connect', () => {
    app.log.info('Redis connected');
  });

  // Static file serving (dashboard UI)
  const __dirname = path.dirname(fileURLToPath(import.meta.url));
  await app.register(fastifyStatic, {
    root: path.join(__dirname, 'ui'),
    prefix: '/ui/',
  });
  app.get('/ui', async (_req, reply) => reply.redirect('/ui/dashboard.html'));

  // Auth plugin (adds tenant context to requests)
  authPlugin(app);

  // Register routes
  agentActionRoutes(app, redis);
  policyRoutes(app);
  approvalRoutes(app);
  webhookRoutes(app);
  stateRoutes(app);
  metricsRoutes(app, redis);

  // Global error handler
  app.setErrorHandler((error: Error & { validation?: unknown; statusCode?: number }, _req, reply) => {
    app.log.error(error);

    if (error.validation) {
      return reply.status(400).send({
        error: 'Validation error',
        message: error.message,
        details: error.validation,
      });
    }

    return reply.status(error.statusCode || 500).send({
      error: error.message || 'Internal server error',
    });
  });

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    app.log.info(`Received ${signal}, shutting down...`);
    await app.close();
    redis.disconnect();
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Start server
  try {
    await app.listen({ port: PORT, host: HOST });
    app.log.info(`Aegis Gateway listening on ${HOST}:${PORT}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

main();
