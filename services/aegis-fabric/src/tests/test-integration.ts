/**
 * Integration test — full flow: create tenant → register agent → create policy → submit action.
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { AegisStorage } from '../storage/aegis-storage.js';
import { TenantRegistry } from '../tenants/tenant-registry.js';
import { AgentRegistry } from '../agents/agent-registry.js';
import { PolicyStore } from '../policies/policy-store.js';
import { PolicyEngine } from '../policies/policy-engine.js';
import { DecisionCache } from '../policies/decision-cache.js';
import { ApprovalQueue } from '../approval/approval-queue.js';
import { ActionProcessor } from '../agents/action-processor.js';
import { AuditLog } from '../events/audit-log.js';
import { UsageTracker } from '../cost/usage-tracker.js';
import { CanonicalAgentAction } from '../core/types.js';
import { generateUUID } from '../core/delta.js';

export async function runIntegrationTests() {
  const errors: string[] = [];
  let passed = 0;
  let failed = 0;

  const tmpDir = path.join(os.tmpdir(), `aegis-test-int-${Date.now()}`);
  const storage = new AegisStorage({ dataDir: tmpDir });
  const tenantRegistry = new TenantRegistry(storage);
  const agentRegistry = new AgentRegistry(storage);
  const policyStore = new PolicyStore(storage);
  const cache = new DecisionCache(1000);
  const policyEngine = new PolicyEngine(policyStore, cache);
  const approvalQueue = new ApprovalQueue(storage);
  const auditLog = new AuditLog(storage);
  const usageTracker = new UsageTracker(storage);

  const actionProcessor = new ActionProcessor({
    storage,
    agentRegistry,
    policyEngine,
    approvalQueue,
    tenantRegistry,
  });

  // Wire usage tracking
  actionProcessor.onUsage((tid, aid, action, tokens, cost) => {
    usageTracker.recordAction(tid, aid, action as any, tokens, cost);
  });

  let tenantId = '';
  let agentId = '';

  // Test 1: Create tenant
  try {
    const { tenant, apiKey } = await tenantRegistry.createTenant({
      name: 'Test Corp', tier: 'STARTER',
    });
    tenantId = tenant.id;
    if (!tenantId) throw new Error('No tenant ID');
    if (!apiKey) throw new Error('No API key');
    if (tenant.data.tier !== 'STARTER') throw new Error('Wrong tier');
    passed++;
  } catch (err) {
    errors.push(`Create tenant: ${err}`);
    failed++;
  }

  // Test 2: Register agent
  try {
    const result = await agentRegistry.registerAgent(tenantId, {
      name: 'Claude Agent', provider: 'claude', version: '3.5',
      capabilities: ['create_task', 'update_task', 'complete_task', 'delete_task', 'query_state'],
    });
    agentId = result.agentId;
    if (!agentId) throw new Error('No agent ID');
    passed++;
  } catch (err) {
    errors.push(`Register agent: ${err}`);
    failed++;
  }

  // Test 3: Submit create_task action (should ALLOW with default policy)
  try {
    cache.clear();
    const action: CanonicalAgentAction = {
      action_id: generateUUID(),
      tenant_id: tenantId,
      agent_id: agentId,
      agent_version: '3.5',
      action: 'create_task',
      params: { title: 'Integration Test Task', priority: 2 },
      metadata: { provider: 'claude', tokens_used: 100, cost_usd: 0.01 },
      timestamp: Date.now(),
    };

    const result = await actionProcessor.process(action);
    if (result.status !== 'executed') throw new Error(`Expected executed, got ${result.status}`);
    if (!result.result?.entity_id) throw new Error('No entity_id in result');
    passed++;
  } catch (err) {
    errors.push(`Create task: ${err}`);
    failed++;
  }

  // Test 4: Add DENY policy and test
  try {
    cache.clear();
    await policyStore.addRule(tenantId, {
      name: 'no-delete',
      description: 'Block delete_task',
      priority: 1,
      conditions: [{ field: 'action', operator: 'eq', value: 'delete_task' }],
      effect: 'DENY',
      reason: 'Delete not allowed in this environment',
      enabled: true,
    });

    const action: CanonicalAgentAction = {
      action_id: generateUUID(),
      tenant_id: tenantId,
      agent_id: agentId,
      agent_version: '3.5',
      action: 'delete_task',
      params: { task_id: 'some-task' },
      metadata: { provider: 'claude' },
      timestamp: Date.now(),
    };

    const result = await actionProcessor.process(action);
    if (result.status !== 'denied') throw new Error(`Expected denied, got ${result.status}`);
    passed++;
  } catch (err) {
    errors.push(`DENY policy: ${err}`);
    failed++;
  }

  // Test 5: Verify audit log has entries
  try {
    const entries = auditLog.getEntries(tenantId);
    // Audit log not wired via onEvent in this test, so check usage instead
    const usage = usageTracker.getUsage(tenantId);
    if (usage.length === 0) throw new Error('Expected usage records');
    const totals = usageTracker.getTenantTotals(tenantId);
    if (totals.actions < 2) throw new Error(`Expected at least 2 actions, got ${totals.actions}`);
    passed++;
  } catch (err) {
    errors.push(`Audit/usage: ${err}`);
    failed++;
  }

  // Test 6: Query state shows the created task
  try {
    const entities = storage.loadEntitiesByType(tenantId, 'aegis_task');
    if (entities.length !== 1) throw new Error(`Expected 1 task, got ${entities.length}`);
    const task = entities[0].state as any;
    if (task.title !== 'Integration Test Task') throw new Error('Wrong task title');
    passed++;
  } catch (err) {
    errors.push(`Query state: ${err}`);
    failed++;
  }

  // Cleanup
  try { fs.rmSync(tmpDir, { recursive: true }); } catch {}

  return { name: 'Integration', passed, failed, errors };
}
