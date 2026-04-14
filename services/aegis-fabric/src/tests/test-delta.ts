/**
 * Tests for delta operations — entity creation, patching, hash chain verification.
 */

import { createEntity, createDelta, applyPatch, verifyHashChain, reconstructState } from '../core/delta.js';
import { AegisTaskData, JsonPatch } from '../core/types.js';

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(`Assertion failed: ${message}`);
}

export async function runDeltaTests() {
  const errors: string[] = [];
  let passed = 0;
  let failed = 0;

  // Test 1: Create entity
  try {
    const taskData: AegisTaskData = {
      tenant_id: 'tenant-1',
      title: 'Test Task',
      description: 'A test task',
      status: 'OPEN',
      priority: 3,
      tags: ['test'],
      assignee: null,
      approval_required: false,
      approval_status: 'NOT_REQUIRED',
      due_at: null,
      linked_entities: [],
      metadata: {},
      created_by: 'agent-1',
      created_at: Date.now(),
      updated_at: Date.now(),
    };

    const { entity, delta, state } = await createEntity('aegis_task', taskData, 'tenant-1');
    assert(entity.entity_id.length > 0, 'entity_id should be set');
    assert(entity.entity_type === 'aegis_task', 'entity_type should be aegis_task');
    assert(entity.current_version === 1, 'version should be 1');
    assert(delta.prev_hash === '0'.repeat(64), 'genesis prev_hash');
    assert(delta.tenant_id === 'tenant-1', 'delta tenant_id');
    assert(state.title === 'Test Task', 'state title');
    passed++;
  } catch (err) {
    errors.push(`Create entity: ${err}`);
    failed++;
  }

  // Test 2: Apply patch
  try {
    const state = { title: 'Old', priority: 3 };
    const patch: JsonPatch[] = [
      { op: 'replace', path: '/title', value: 'New' },
      { op: 'replace', path: '/priority', value: 1 },
    ];
    const newState = applyPatch(state, patch);
    assert(newState.title === 'New', 'title should be updated');
    assert(newState.priority === 1, 'priority should be updated');
    assert(state.title === 'Old', 'original should be unchanged');
    passed++;
  } catch (err) {
    errors.push(`Apply patch: ${err}`);
    failed++;
  }

  // Test 3: Create delta (mutation with hash chain)
  try {
    const taskData: AegisTaskData = {
      tenant_id: 'tenant-1', title: 'Task', description: '', status: 'OPEN',
      priority: 3, tags: [], assignee: null, approval_required: false,
      approval_status: 'NOT_REQUIRED', due_at: null, linked_entities: [],
      metadata: {}, created_by: 'agent-1', created_at: Date.now(), updated_at: Date.now(),
    };
    const { entity, delta: d1 } = await createEntity('aegis_task', taskData, 'tenant-1');

    const patch: JsonPatch[] = [{ op: 'replace', path: '/title', value: 'Updated Task' }];
    const { entity: e2, delta: d2, state: s2 } = await createDelta(
      entity, taskData as unknown as Record<string, unknown>, patch, 'agent', 'tenant-1'
    );

    assert(e2.current_version === 2, 'version should be 2');
    assert(d2.prev_hash === d1.new_hash, 'prev_hash should chain');
    assert((s2 as any).title === 'Updated Task', 'state should be updated');
    passed++;
  } catch (err) {
    errors.push(`Create delta: ${err}`);
    failed++;
  }

  // Test 4: Hash chain verification
  try {
    const taskData: AegisTaskData = {
      tenant_id: 'tenant-1', title: 'Chain', description: '', status: 'OPEN',
      priority: 3, tags: [], assignee: null, approval_required: false,
      approval_status: 'NOT_REQUIRED', due_at: null, linked_entities: [],
      metadata: {}, created_by: 'agent-1', created_at: Date.now(), updated_at: Date.now(),
    };
    const { entity, delta: d1 } = await createEntity('aegis_task', taskData, 'tenant-1');

    const patch: JsonPatch[] = [{ op: 'replace', path: '/title', value: 'V2' }];
    const { entity: e2, delta: d2 } = await createDelta(
      entity, taskData as unknown as Record<string, unknown>, patch, 'agent', 'tenant-1'
    );

    const valid = await verifyHashChain([d1, d2]);
    assert(valid === true, 'hash chain should be valid');

    // Tamper and verify
    const tampered = { ...d2, new_hash: 'bad' + d2.new_hash.slice(3) };
    const invalid = await verifyHashChain([d1, tampered]);
    assert(invalid === false, 'tampered chain should fail');
    passed++;
  } catch (err) {
    errors.push(`Hash chain: ${err}`);
    failed++;
  }

  // Test 5: State reconstruction
  try {
    const taskData: AegisTaskData = {
      tenant_id: 'tenant-1', title: 'Original', description: '', status: 'OPEN',
      priority: 3, tags: [], assignee: null, approval_required: false,
      approval_status: 'NOT_REQUIRED', due_at: null, linked_entities: [],
      metadata: {}, created_by: 'agent-1', created_at: Date.now(), updated_at: Date.now(),
    };
    const { entity, delta: d1 } = await createEntity('aegis_task', taskData, 'tenant-1');

    const { delta: d2 } = await createDelta(
      entity, taskData as unknown as Record<string, unknown>,
      [{ op: 'replace', path: '/title', value: 'Reconstructed' }], 'agent', 'tenant-1'
    );

    const rebuilt = reconstructState<AegisTaskData>([d1, d2]);
    assert(rebuilt.title === 'Reconstructed', 'reconstructed state should match');
    passed++;
  } catch (err) {
    errors.push(`Reconstruct: ${err}`);
    failed++;
  }

  return { name: 'Delta Operations', passed, failed, errors };
}
