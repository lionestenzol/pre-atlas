/**
 * SignalsStore unit tests · Ship Target #1.
 * Run with: npx tsx src/tests/signals-store-tests.ts
 *
 * Hits the SQLite-backed SignalsStore directly with a temp dataDir.
 * No HTTP server required.
 */
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { SignalsStore, SignalValidationError } from '../atlas/signals-store.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void): void {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    passed++;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.log(`  [FAIL] ${name}\n    ${msg}`);
    failed++;
  }
}

function assert(cond: boolean, message: string): void {
  if (!cond) throw new Error(message);
}

function tempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'signals-store-test-'));
}

function makeSignal(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: '1.0',
    id: 'sig_' + Math.random().toString(36).slice(2, 14),
    emitted_at: new Date().toISOString(),
    source_layer: 'optogon',
    signal_type: 'completion',
    priority: 'normal',
    payload: {
      label: 'Test signal',
      summary: 'Unit test payload',
      action_required: false,
    },
    ...overrides,
  };
}

console.log('=== SignalsStore Tests ===\n');

test('ingests and lists a valid signal', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  const sig = makeSignal();
  store.ingest(sig);
  const listed = store.list();
  assert(listed.length === 1, `expected 1 signal, got ${listed.length}`);
  assert(listed[0].id === sig.id, 'returned signal has wrong id');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('rejects payload missing schema_version', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  const bad = makeSignal();
  delete (bad as Record<string, unknown>).schema_version;
  let threw = false;
  try {
    store.ingest(bad);
  } catch (err) {
    if (err instanceof SignalValidationError) threw = true;
  }
  assert(threw, 'expected SignalValidationError for missing schema_version');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('rejects approval_required without action_options', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  const bad = makeSignal({
    signal_type: 'approval_required',
    payload: { label: 'X', summary: 'Y', action_required: true },
  });
  let threw = false;
  try {
    store.ingest(bad);
  } catch (err) {
    if (err instanceof SignalValidationError) threw = true;
  }
  assert(threw, 'approval_required with no action_options must fail validation');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('list returns newest first', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  const a = makeSignal({ id: 'sig_a', emitted_at: '2026-04-27T10:00:00Z' });
  const b = makeSignal({ id: 'sig_b', emitted_at: '2026-04-27T11:00:00Z' });
  store.ingest(a);
  store.ingest(b);
  const listed = store.list();
  assert(listed[0].id === 'sig_b', `expected sig_b first, got ${listed[0].id}`);
  assert(listed[1].id === 'sig_a', `expected sig_a second, got ${listed[1].id}`);
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('list(since) filters by emitted_at', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  store.ingest(makeSignal({ id: 'sig_old', emitted_at: '2026-04-27T10:00:00Z' }));
  store.ingest(makeSignal({ id: 'sig_new', emitted_at: '2026-04-27T11:00:00Z' }));
  const listed = store.list('2026-04-27T10:30:00Z');
  assert(listed.length === 1, `expected 1 signal after since, got ${listed.length}`);
  assert(listed[0].id === 'sig_new', 'wrong signal returned');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('resolve marks resolved without deleting', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  const approval = makeSignal({
    id: 'sig_approve',
    signal_type: 'approval_required',
    priority: 'urgent',
    payload: {
      label: 'Approve?',
      summary: 'commit a file',
      action_required: true,
      action_options: [
        { id: 'approve', label: 'Approve', risk_tier: 'medium' },
        { id: 'deny', label: 'Deny', risk_tier: 'low' },
      ],
    },
  });
  store.ingest(approval);
  const res = store.resolve('sig_approve', 'approve');
  assert(res !== null, 'expected resolution');
  assert(res?.action_id === 'approve', 'wrong action_id');
  // No longer in active list
  const listed = store.list();
  assert(listed.length === 0, `expected no active signals, got ${listed.length}`);
  // But still in resolutions
  const resolutions = store.listResolutions();
  assert(resolutions.length === 1, 'expected one resolution recorded');
  assert(resolutions[0].signal_id === 'sig_approve', 'wrong resolution id');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('resolve unknown id returns null', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  const res = store.resolve('sig_nonexistent', 'approve');
  assert(res === null, 'expected null for unknown signal');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('resolving twice returns null on second attempt', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  store.ingest(makeSignal({
    id: 'sig_dup',
    signal_type: 'approval_required',
    payload: {
      label: 'X', summary: 'Y', action_required: true,
      action_options: [{ id: 'a', label: 'A', risk_tier: 'low' }],
    },
  }));
  const first = store.resolve('sig_dup', 'a');
  const second = store.resolve('sig_dup', 'a');
  assert(first !== null, 'first resolve should succeed');
  assert(second === null, 'second resolve should be null');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('persists across store close + reopen', () => {
  const dir = tempDir();
  const a = new SignalsStore(dir, repoRoot);
  a.ingest(makeSignal({ id: 'sig_persist', emitted_at: '2026-04-27T12:00:00Z' }));
  a.close();
  const b = new SignalsStore(dir, repoRoot);
  const listed = b.list();
  assert(listed.length === 1, `expected 1 signal after reopen, got ${listed.length}`);
  assert(listed[0].id === 'sig_persist', 'wrong signal after reopen');
  b.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

test('clearAll removes signals and resolutions', () => {
  const dir = tempDir();
  const store = new SignalsStore(dir, repoRoot);
  store.ingest(makeSignal({ id: 'sig_x' }));
  store.clearAll();
  assert(store.list().length === 0, 'list should be empty');
  assert(store.listResolutions().length === 0, 'resolutions should be empty');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

console.log(`\n${passed} passed, ${failed} failed.`);
process.exit(failed > 0 ? 1 : 0);
