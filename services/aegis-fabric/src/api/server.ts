/**
 * Aegis Enterprise Fabric — API Server
 *
 * Express entry point on port 3002. Wires all components together.
 */

import express from 'express';
import cors from 'cors';
import * as path from 'path';
import { fileURLToPath } from 'url';

// Core
import { AegisStorage } from '../storage/aegis-storage.js';
import { SnapshotManager } from '../storage/snapshot-manager.js';

// Tenants
import { TenantRegistry } from '../tenants/tenant-registry.js';

// Gateway
import {
  requestIdMiddleware, authMiddleware, rateLimitMiddleware, responseLogMiddleware,
} from '../gateway/api-middleware.js';
import { RateLimiter } from '../gateway/rate-limiter.js';
import { RequestLogger } from '../gateway/request-logger.js';

// Agents
import { AgentRegistry } from '../agents/agent-registry.js';
import { ActionProcessor } from '../agents/action-processor.js';

// Policies
import { PolicyStore } from '../policies/policy-store.js';
import { PolicyEngine } from '../policies/policy-engine.js';
import { DecisionCache } from '../policies/decision-cache.js';

// Approval
import { ApprovalQueue } from '../approval/approval-queue.js';

// Events
import { AegisEventBus } from '../events/event-bus.js';
import { WebhookDispatcher } from '../events/webhook-dispatcher.js';
import { AuditLog } from '../events/audit-log.js';

// Observability & Cost
import { UsageTracker } from '../cost/usage-tracker.js';
import { logger } from '../observability/logger.js';
import { metrics } from '../observability/metrics.js';

// Routes
import { tenantRoutes } from './routes/tenant-routes.js';
import { agentRoutes } from './routes/agent-routes.js';
import { policyRoutes } from './routes/policy-routes.js';
import { stateRoutes } from './routes/state-routes.js';
import { approvalRoutes } from './routes/approval-routes.js';
import { webhookRoutes } from './routes/webhook-routes.js';
import { metricsRoutes } from './routes/metrics-routes.js';
import { deltaRoutes } from './routes/delta-routes.js';

// === CONFIG ===

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = Number(process.env.AEGIS_PORT) || 3002;
const DATA_DIR = process.env.AEGIS_DATA_DIR || path.resolve(__dirname, '../../.aegis-data');

// === INITIALIZE COMPONENTS ===

const storage = new AegisStorage({ dataDir: DATA_DIR });
const snapshotManager = new SnapshotManager(storage);
const tenantRegistry = new TenantRegistry(storage);
const rateLimiter = new RateLimiter();
const requestLogger = new RequestLogger(storage);
const agentRegistry = new AgentRegistry(storage);
const policyStore = new PolicyStore(storage);
const decisionCache = new DecisionCache(60_000);
const policyEngine = new PolicyEngine(policyStore, decisionCache);
const approvalQueue = new ApprovalQueue(storage);
const eventBus = new AegisEventBus();
const webhookDispatcher = new WebhookDispatcher(storage, eventBus);
const auditLog = new AuditLog(storage);
const usageTracker = new UsageTracker(storage);

const actionProcessor = new ActionProcessor({
  storage,
  agentRegistry,
  policyEngine,
  approvalQueue,
  tenantRegistry,
});

// Wire event handlers
actionProcessor.onEvent((event, data) => {
  eventBus.emit(event, data);
});

actionProcessor.onUsage((tenantId, agentId, action, tokens, cost) => {
  usageTracker.recordAction(tenantId, agentId, action as any, tokens, cost);
});

// === EXPRESS APP ===

const app = express();

app.use(cors());
app.use(express.json());

// Serve dashboard UI (before auth middleware so it's publicly accessible)
app.use('/ui', express.static(path.resolve(__dirname, '../../src/ui')));

// Middleware chain
app.use(requestIdMiddleware);
app.use(responseLogMiddleware(requestLogger));
app.use(authMiddleware(tenantRegistry));
app.use(rateLimitMiddleware(rateLimiter));

// Mount routes
app.use(tenantRoutes(tenantRegistry));
app.use(agentRoutes(agentRegistry, actionProcessor, rateLimiter, auditLog));
app.use(policyRoutes(policyStore, policyEngine, agentRegistry, tenantRegistry));
app.use(stateRoutes(storage, snapshotManager));
app.use(approvalRoutes(approvalQueue, actionProcessor));
app.use(webhookRoutes(webhookDispatcher));
app.use(metricsRoutes(usageTracker, storage, tenantRegistry));
app.use(deltaRoutes(storage));

// === START ===

app.listen(PORT, () => {
  logger.info(`Aegis Enterprise Fabric started`, { port: PORT, data_dir: DATA_DIR });
  logger.info(`Endpoints: http://localhost:${PORT}/health | http://localhost:${PORT}/metrics`);
  metrics.setGauge('aegis_active_tenants', tenantRegistry.getTenantCount());
  eventBus.emit('system.startup', { port: PORT, timestamp: Date.now() });
});
