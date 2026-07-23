/**
 * PKT-008 verification: droplist signals -> Lattice viewmodel projection.
 *
 * Pure unit tests against the in-process buildViewmodel function. No HTTP
 * server, no SQLite, no FS — uses a mock StorageLike + a non-existent
 * cognitiveSensorDir so readRegistry returns null.
 *
 * Run with: npx tsx src/tests/lattice-projection-droplist-tests.ts
 */

import { buildViewmodel, type StorageLike } from '../atlas/lattice-projection.js';
import type { Signal } from '../atlas/signals-store.js';
import type { Entity } from '../core/types-core.js';

interface TestResult { name: string; passed: boolean; error?: string }

const results: TestResult[] = [];

function test(name: string, fn: () => void): void {
  try {
    fn();
    results.push({ name, passed: true });
    console.log(`  [PASS] ${name}`);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    results.push({ name, passed: false, error: message });
    console.log(`  [FAIL] ${name} — ${message}`);
  }
}

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

// === Helpers ===

const MISSING_DIR = '__pkt008_no_such_dir__';

function makeSignal(overrides: Partial<Signal> & { payloadOverrides?: Partial<Signal['payload']> }): Signal {
  const { payloadOverrides, ...rest } = overrides;
  return {
    schema_version: '1.0',
    id: 'sig_default',
    emitted_at: new Date().toISOString(),
    source_layer: 'optogon',
    signal_type: 'completion',
    priority: 'normal',
    payload: {
      task_id: 'drop_default',
      label: 'Default droplist label',
      summary: 'Default summary',
      data: { dag_id: 'dag_default' },
      ...payloadOverrides,
    },
    ...rest,
  } as Signal;
}

function mockStorage(opts: {
  signals?: Signal[];
  taskEntities?: Array<{ entity: Entity; state: Record<string, unknown> }>;
}): StorageLike {
  return {
    loadEntitiesByType<T>(type: string): Array<{ entity: Entity; state: T }> {
      if (type === 'task') {
        return (opts.taskEntities ?? []) as unknown as Array<{ entity: Entity; state: T }>;
      }
      return [];
    },
    saveEntity(): void { /* no-op */ },
    appendDelta(): void { /* no-op */ },
    loadSignals: () => opts.signals ?? [],
  };
}

// === Tests ===

function runTests(): void {
  console.log('=== PKT-008 lattice-projection droplist tests ===\n');

  // Fixture 1 (regression guard for OQ-19 pre-state):
  // empty signals + missing registry -> empty items.
  test('regression: no signals, no registry -> empty items', () => {
    const storage = mockStorage({ signals: [] });
    const vm = buildViewmodel(MISSING_DIR, storage);
    assert(vm.items.length === 0, `expected 0 items, got ${vm.items.length}`);
    assert(vm.projects.length > 0, 'projects array should still be seeded');
  });

  // Fixture 2: one droplist signal -> exactly one item with provenance=droplist.
  test('one droplist signal projects to one item with provenance=droplist', () => {
    const sig = makeSignal({
      id: 'sig_abc123',
      signal_type: 'completion',
      payloadOverrides: {
        task_id: 'drop_2681d50fd332',
        label: 'Check the subject and log the observation',
        summary: 'animal/property: 3/3 done; status=complete',
        data: { dag_id: 'dag_xyz' },
      },
    });
    const vm = buildViewmodel(MISSING_DIR, mockStorage({ signals: [sig] }));
    assert(vm.items.length === 1, `expected 1 item, got ${vm.items.length}`);
    const item = vm.items[0];
    assert(item.id === 'drop_2681d50fd332', `id wrong: ${item.id}`);
    assert(item.title.startsWith('Check'), `title wrong: ${item.title}`);
    assert(item.provenance.source === 'droplist', `provenance wrong: ${item.provenance.source}`);
    assert(item.status === 'done', `completion should map to done, got ${item.status}`);
    assert(item.project === 'atlas', `project should default to atlas, got ${item.project}`);
  });

  // Fixture 3: user correction over droplist item -> provenance flips to user.
  test('user correction over droplist item flips provenance to user', () => {
    const sig = makeSignal({
      id: 'sig_qrs',
      signal_type: 'completion',
      payloadOverrides: {
        task_id: 'drop_corrected',
        label: 'droplist originally',
        summary: '...',
        data: { dag_id: 'dag_q' },
      },
    });
    const taskEntities = [{
      entity: { entity_id: 't_1', entity_type: 'task', schema_version: '1.0' } as unknown as Entity,
      state: {
        cortex_metadata: {
          source: 'lattice',
          lattice_item_id: 'drop_corrected',
          original_project: 'atlas',
          original_status: 'done',
          corrected_at: '2026-06-15T12:00:00.000Z',
        },
        project: 'property',
        lattice_status: 'active',
      },
    }];
    const vm = buildViewmodel(MISSING_DIR, mockStorage({ signals: [sig], taskEntities }));
    assert(vm.items.length === 1, `expected 1 item, got ${vm.items.length}`);
    const item = vm.items[0];
    assert(item.provenance.source === 'user', `should flip to user, got ${item.provenance.source}`);
    assert(item.project === 'property', `project should be corrected to property, got ${item.project}`);
    assert(item.status === 'active', `status should be corrected to active, got ${item.status}`);
    assert(typeof item.provenance.correctedAt === 'string', 'correctedAt should be set');
  });

  // Fixture 4: status mapping matrix.
  test('signal_type mapping: completion->done', () => {
    const vm = buildViewmodel(MISSING_DIR, mockStorage({
      signals: [makeSignal({ id: 's', signal_type: 'completion' })],
    }));
    assert(vm.items[0].status === 'done', `got ${vm.items[0].status}`);
  });

  test('signal_type mapping: error->blocked', () => {
    const vm = buildViewmodel(MISSING_DIR, mockStorage({
      signals: [makeSignal({ id: 's', signal_type: 'error' })],
    }));
    assert(vm.items[0].status === 'blocked', `got ${vm.items[0].status}`);
  });

  test('signal_type mapping: approval_required->blocked', () => {
    const sig = makeSignal({
      id: 's',
      signal_type: 'approval_required',
      payloadOverrides: {
        task_id: 'drop_a',
        label: 'L',
        summary: 'S',
        data: { dag_id: 'd' },
        action_required: true,
        action_options: [{ id: 'opt1', label: 'opt1', risk_tier: 'low' }],
      },
    });
    const vm = buildViewmodel(MISSING_DIR, mockStorage({ signals: [sig] }));
    assert(vm.items[0].status === 'blocked', `got ${vm.items[0].status}`);
  });

  test('signal_type mapping: blocked->blocked', () => {
    const vm = buildViewmodel(MISSING_DIR, mockStorage({
      signals: [makeSignal({ id: 's', signal_type: 'blocked' })],
    }));
    assert(vm.items[0].status === 'blocked', `got ${vm.items[0].status}`);
  });

  test('signal_type mapping: status->active', () => {
    const vm = buildViewmodel(MISSING_DIR, mockStorage({
      signals: [makeSignal({ id: 's', signal_type: 'status' })],
    }));
    assert(vm.items[0].status === 'active', `got ${vm.items[0].status}`);
  });

  test('signal_type mapping: insight->open', () => {
    const vm = buildViewmodel(MISSING_DIR, mockStorage({
      signals: [makeSignal({ id: 's', signal_type: 'insight' })],
    }));
    assert(vm.items[0].status === 'open', `got ${vm.items[0].status}`);
  });

  // Non-droplist signal (no dag_id marker) must NOT be projected.
  test('signal without payload.data.dag_id is filtered out', () => {
    const sig = makeSignal({
      id: 'sig_other',
      payloadOverrides: {
        task_id: 'drop_x',
        label: 'not a droplist DAG',
        summary: 'comes from another producer',
        data: { some_other: 'marker' },  // no dag_id
      },
    });
    const vm = buildViewmodel(MISSING_DIR, mockStorage({ signals: [sig] }));
    assert(vm.items.length === 0, `expected non-droplist signal filtered out, got ${vm.items.length} items`);
  });

  // Graph projection: every item also lands as a node with belongs_to edge.
  test('droplist item appears in nodes + belongs_to edge', () => {
    const sig = makeSignal({
      id: 's',
      payloadOverrides: {
        task_id: 'drop_graph',
        label: 'L',
        summary: 'S',
        data: { dag_id: 'd' },
      },
    });
    const vm = buildViewmodel(MISSING_DIR, mockStorage({ signals: [sig] }));
    const itemNode = vm.nodes.find((n) => n.id === 'drop_graph');
    assert(itemNode !== undefined, 'expected node for droplist item');
    assert(itemNode!.type === 'item', `node type wrong: ${itemNode!.type}`);
    assert(itemNode!.provenance?.source === 'droplist', 'node provenance should be droplist');
    const belongsTo = vm.edges.find(
      (e) => e.from === 'drop_graph' && e.to === 'project:atlas' && e.kind === 'belongs_to',
    );
    assert(belongsTo !== undefined, 'expected belongs_to edge to project:atlas');
  });

  // R1 regression guard: multiple signals for the same task_id dedup to
  // the newest by emitted_at, so a replayed DAG (running -> completion)
  // surfaces as one row at its latest state, not two.
  test('multiple signals per task_id dedup, newest emitted_at wins', () => {
    const taskId = 'drop_replayed';
    const older = makeSignal({
      id: 'sig_old',
      emitted_at: '2026-06-15T10:00:00.000Z',
      signal_type: 'status',
      payloadOverrides: {
        task_id: taskId,
        label: 'running snapshot',
        summary: 's',
        data: { dag_id: 'd' },
      },
    });
    const newer = makeSignal({
      id: 'sig_new',
      emitted_at: '2026-06-15T11:00:00.000Z',
      signal_type: 'completion',
      payloadOverrides: {
        task_id: taskId,
        label: 'completed snapshot',
        summary: 's',
        data: { dag_id: 'd' },
      },
    });
    // Ring order is irrelevant — dedup picks newest by emitted_at, not by index.
    const vm = buildViewmodel(MISSING_DIR, mockStorage({ signals: [newer, older] }));
    assert(vm.items.length === 1, `expected 1 deduped item, got ${vm.items.length}`);
    assert(vm.items[0].id === taskId, `id wrong: ${vm.items[0].id}`);
    assert(vm.items[0].title === 'completed snapshot', `should show newest title, got ${vm.items[0].title}`);
    assert(vm.items[0].status === 'done', `should reflect newest signal_type=completion, got ${vm.items[0].status}`);
  });

  test('two different task_ids both project (dedup is per-key)', () => {
    const sigA = makeSignal({
      id: 'sig_a',
      payloadOverrides: { task_id: 'drop_A', label: 'A', summary: 's', data: { dag_id: 'a' } },
    });
    const sigB = makeSignal({
      id: 'sig_b',
      payloadOverrides: { task_id: 'drop_B', label: 'B', summary: 's', data: { dag_id: 'b' } },
    });
    const vm = buildViewmodel(MISSING_DIR, mockStorage({ signals: [sigA, sigB] }));
    assert(vm.items.length === 2, `expected 2 items, got ${vm.items.length}`);
    const ids = vm.items.map((i) => i.id).sort();
    assert(ids[0] === 'drop_A' && ids[1] === 'drop_B', `wrong ids: ${ids.join(',')}`);
  });

  // Backward compat: when loadSignals is absent (e.g. test fixtures or the
  // recordCorrection path), the projection still works.
  test('storage without loadSignals still builds viewmodel', () => {
    const storage: StorageLike = {
      loadEntitiesByType: () => [],
      saveEntity: () => undefined,
      appendDelta: () => undefined,
      // no loadSignals
    };
    const vm = buildViewmodel(MISSING_DIR, storage);
    assert(vm.items.length === 0, `expected 0 items, got ${vm.items.length}`);
  });

  // === Summary ===
  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;
  console.log(`\nResults: ${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

runTests();
