/**
 * Delta Kernel — Fastify Entry Point
 *
 * Stateful service backed by PostgreSQL (per-tenant databases).
 * Serves all CRUD operations for the Aegis Delta Fabric.
 * Port: 3001
 */

import Fastify from 'fastify';
import cors from '@fastify/cors';
import { PoolManager } from './db/pool-manager.js';
import { SnapshotService } from './services/snapshot-service.js';
import { healthRoutes } from './routes/health.js';
import { tenantRoutes } from './routes/tenants.js';
import { agentRoutes } from './routes/agents.js';
import { deltaRoutes } from './routes/delta.js';
import { stateRoutes } from './routes/state.js';
import { policyRoutes } from './routes/policies.js';
import { approvalRoutes } from './routes/approvals.js';
import { webhookRoutes } from './routes/webhooks.js';
import { auditRoutes } from './routes/audit.js';
import { usageRoutes } from './routes/usage.js';

const PORT = Number(process.env.KERNEL_PORT) || 3001;
const HOST = process.env.KERNEL_HOST || '0.0.0.0';

async function main(): Promise<void> {
  const app = Fastify({
    logger: {
      level: process.env.LOG_LEVEL || 'info',
    },
  });

  // CORS (allow dashboard on Gateway port to call Kernel)
  await app.register(cors, { origin: true });

  // Initialize PostgreSQL pool manager
  const poolManager = new PoolManager();

  // Initialize snapshot service
  const snapshotService = new SnapshotService();

  // Register routes
  healthRoutes(app, poolManager);
  tenantRoutes(app, poolManager);
  agentRoutes(app, poolManager);
  deltaRoutes(app, poolManager);
  stateRoutes(app, poolManager);
  policyRoutes(app, poolManager);
  approvalRoutes(app, poolManager);
  webhookRoutes(app, poolManager);
  auditRoutes(app, poolManager);
  usageRoutes(app, poolManager);

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
    snapshotService.stop();
    await app.close();
    await poolManager.closeAll();
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Start server
  try {
    // Verify database connectivity before starting
    const health = await poolManager.healthCheck();
    if (!health.connected) {
      app.log.error('Failed to connect to PostgreSQL. Is the database running?');
      process.exit(1);
    }

    await app.listen({ port: PORT, host: HOST });
    app.log.info(`Delta Kernel listening on ${HOST}:${PORT}`);

    // Start snapshot service (background task)
    // It needs access to tenant pools — we pass a getter that reads from poolManager
    // Note: tenant pools are lazily created, so this starts empty and picks up as requests come in
    snapshotService.start(() => {
      // PoolManager doesn't expose tenantPools directly,
      // so snapshot service runs per-request via maybeSnapshot
      return new Map();
    });
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

main();
