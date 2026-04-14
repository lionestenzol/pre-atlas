/**
 * Tests for approval queue — submit, list, decide, expire.
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { AegisStorage } from '../storage/aegis-storage.js';
import { ApprovalQueue } from '../approval/approval-queue.js';
import { CanonicalAgentAction } from '../core/types.js';
import { generateUUID } from '../core/delta.js';

export async function runApprovalTests() {
  const errors: string[] = [];
  let passed = 0;
  let failed = 0;

  const tmpDir = path.join(os.tmpdir(), `aegis-test-approval-${Date.now()}`);
  const storage = new AegisStorage({ dataDir: tmpDir });
  const queue = new ApprovalQueue(storage);
  const tenantId = 'test-tenant';

  const makeAction = (): CanonicalAgentAction => ({
    action_id: generateUUID(),
    tenant_id: tenantId,
    agent_id: 'agent-1',
    agent_version: '1.0.0',
    action: 'create_task',
    params: { title: 'Needs Approval' },
    metadata: { provider: 'claude' },
    timestamp: Date.now(),
  });

  // Test 1: Submit creates pending approval
  try {
    const action = makeAction();
    const { approvalId } = await queue.submit(action);
    if (!approvalId) throw new Error('No approvalId returned');

    const pending = queue.listPending(tenantId);
    if (pending.length !== 1) throw new Error(`Expected 1 pending, got ${pending.length}`);
    if (pending[0].data.status !== 'PENDING') throw new Error('Status should be PENDING');
    passed++;
  } catch (err) {
    errors.push(`Submit: ${err}`);
    failed++;
  }

  // Test 2: Approve
  try {
    const pending = queue.listPending(tenantId);
    const id = pending[0].entity.entity_id;
    const result = queue.decide(tenantId, id, 'APPROVED', 'test-user', 'Looks good');
    if (!result) throw new Error('Decide returned null');
    if (result.status !== 'APPROVED') throw new Error('Should be APPROVED');
    if (result.decided_by !== 'test-user') throw new Error('Wrong decidedBy');

    const remaining = queue.listPending(tenantId);
    if (remaining.length !== 0) throw new Error('No more pending after approval');
    passed++;
  } catch (err) {
    errors.push(`Approve: ${err}`);
    failed++;
  }

  // Test 3: Reject
  try {
    const action = makeAction();
    const { approvalId } = await queue.submit(action);
    const result = queue.decide(tenantId, approvalId, 'REJECTED', 'test-admin', 'Too risky');
    if (!result) throw new Error('Decide returned null');
    if (result.status !== 'REJECTED') throw new Error('Should be REJECTED');
    passed++;
  } catch (err) {
    errors.push(`Reject: ${err}`);
    failed++;
  }

  // Test 4: Cannot decide on already decided approval
  try {
    const pending = queue.listPending(tenantId);
    // All should be decided by now — submit a new one and decide twice
    const action = makeAction();
    const { approvalId } = await queue.submit(action);
    queue.decide(tenantId, approvalId, 'APPROVED', 'user1');
    const secondResult = queue.decide(tenantId, approvalId, 'REJECTED', 'user2');
    if (secondResult !== null) throw new Error('Second decide should return null');
    passed++;
  } catch (err) {
    errors.push(`Double decide: ${err}`);
    failed++;
  }

  // Cleanup
  try { fs.rmSync(tmpDir, { recursive: true }); } catch {}

  return { name: 'Approval Queue', passed, failed, errors };
}
