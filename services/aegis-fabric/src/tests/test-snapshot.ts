/**
 * Tests for snapshot manager — create snapshots, rebuild state, point-in-time queries.
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { AegisStorage } from '../storage/aegis-storage.js';
import { SnapshotManager } from '../storage/snapshot-manager.js';
import { createEntity, createDelta, now } from '../core/delta.js';
import { AegisTaskData, JsonPatch } from '../core/types.js';

export async function runSnapshotTests() {
  const errors: string[] = [];
  let passed = 0;
  let failed = 0;

  const tmpDir = path.join(os.tmpdir(), `aegis-test-snap-${Date.now()}`);
  const storage = new AegisStorage({ dataDir: tmpDir });
  const snapshotMgr = new SnapshotManager(storage, 3);  // snapshot every 3 deltas for testing
  const tenantId = 'test-tenant';

  // Create some entities and deltas
  const taskData: AegisTaskData = {
    tenant_id: tenantId, title: 'Snap Task', description: '', status: 'OPEN',
    priority: 3, tags: [], assignee: null, approval_required: false,
    approval_status: 'NOT_REQUIRED', due_at: null, linked_entities: [],
    metadata: {}, created_by: 'agent-1', created_at: Date.now(), updated_at: Date.now(),
  };

  // Test 1: shouldSnapshot = false when under threshold
  try {
    const { entity, delta } = await createEntity('aegis_task', taskData, tenantId);
    storage.saveEntity(tenantId, entity, taskData);
    storage.appendDelta(tenantId, delta);

    if (snapshotMgr.shouldSnapshot(tenantId)) throw new Error('Should not snapshot with 1 delta');
    passed++;
  } catch (err) {
    errors.push(`Under threshold: ${err}`);
    failed++;
  }

  // Test 2: shouldSnapshot = true when over threshold
  try {
    // Add 2 more deltas to hit threshold of 3
    const { entity: e2, delta: d2 } = await createEntity('aegis_task', { ...taskData, title: 'Task 2' }, tenantId);
    storage.saveEntity(tenantId, e2, { ...taskData, title: 'Task 2' });
    storage.appendDelta(tenantId, d2);

    const { entity: e3, delta: d3 } = await createEntity('aegis_task', { ...taskData, title: 'Task 3' }, tenantId);
    storage.saveEntity(tenantId, e3, { ...taskData, title: 'Task 3' });
    storage.appendDelta(tenantId, d3);

    if (!snapshotMgr.shouldSnapshot(tenantId)) throw new Error('Should snapshot with 3 deltas');
    passed++;
  } catch (err) {
    errors.push(`Over threshold: ${err}`);
    failed++;
  }

  // Test 3: Create snapshot
  try {
    const snapshot = await snapshotMgr.createSnapshot(tenantId);
    if (snapshot.delta_count !== 3) throw new Error(`Expected 3 deltas, got ${snapshot.delta_count}`);
    if (snapshot.entities.length !== 3) throw new Error(`Expected 3 entities, got ${snapshot.entities.length}`);

    const snapshots = snapshotMgr.listSnapshots(tenantId);
    if (snapshots.length !== 1) throw new Error('Should have 1 snapshot');
    passed++;
  } catch (err) {
    errors.push(`Create snapshot: ${err}`);
    failed++;
  }

  // Test 4: Rebuild state from snapshot
  try {
    const rebuilt = snapshotMgr.rebuildState(tenantId);
    if (rebuilt.size !== 3) throw new Error(`Expected 3 entities in rebuilt state, got ${rebuilt.size}`);
    passed++;
  } catch (err) {
    errors.push(`Rebuild: ${err}`);
    failed++;
  }

  // Cleanup
  try { fs.rmSync(tmpDir, { recursive: true }); } catch {}

  return { name: 'Snapshot Manager', passed, failed, errors };
}
