/**
 * Delta-Kernel API Endpoint Tests
 *
 * Boots the Express server and hits key endpoints.
 * Run with: npx tsx src/tests/api-tests.ts
 */

const BASE = 'http://localhost:3001';

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

const results: TestResult[] = [];

async function test(name: string, fn: () => Promise<void>): Promise<void> {
  try {
    await fn();
    results.push({ name, passed: true });
    console.log(`  [PASS] ${name}`);
  } catch (err: any) {
    results.push({ name, passed: false, error: err.message });
    console.log(`  [FAIL] ${name} — ${err.message}`);
  }
}

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

async function fetchJSON(path: string, options?: RequestInit): Promise<{ status: number; body: any }> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await res.json();
  return { status: res.status, body };
}

// ============================================================
// Tests
// ============================================================

async function runTests(): Promise<void> {
  console.log('=== Delta-Kernel API Tests ===\n');

  // Wait for server to be available
  let serverReady = false;
  for (let i = 0; i < 10; i++) {
    try {
      await fetch(`${BASE}/api/state`);
      serverReady = true;
      break;
    } catch {
      await new Promise(r => setTimeout(r, 1000));
    }
  }

  if (!serverReady) {
    console.log('[SKIP] Server not available at localhost:3001. Start with: npm run api');
    process.exit(0);
  }

  // --- GET /api/state/unified ---
  await test('GET /api/state/unified returns 200 with derived.mode', async () => {
    const { status, body } = await fetchJSON('/api/state/unified');
    assert(status === 200, `Expected 200, got ${status}`);
    assert(body.derived !== undefined, 'Missing derived field');
    assert(typeof body.derived.mode === 'string', 'derived.mode is not a string');
    assert(['RECOVER', 'CLOSURE', 'MAINTENANCE', 'BUILD', 'COMPOUND', 'SCALE'].includes(body.derived.mode),
      `Invalid mode: ${body.derived.mode}`);
  });

  await test('GET /api/state/unified has build_allowed', async () => {
    const { body } = await fetchJSON('/api/state/unified');
    assert(typeof body.derived.build_allowed === 'boolean', 'build_allowed is not boolean');
  });

  await test('GET /api/state/unified has closure metrics', async () => {
    const { body } = await fetchJSON('/api/state/unified');
    assert(typeof body.derived.open_loops === 'number', 'open_loops missing or not number');
    assert(typeof body.derived.closure_ratio === 'number', 'closure_ratio missing or not number');
  });

  // --- GET /api/state ---
  await test('GET /api/state returns 200', async () => {
    const { status } = await fetchJSON('/api/state');
    assert(status === 200, `Expected 200, got ${status}`);
  });

  // --- GET /api/tasks ---
  await test('GET /api/tasks returns 200 with array', async () => {
    const { status, body } = await fetchJSON('/api/tasks');
    assert(status === 200, `Expected 200, got ${status}`);
    assert(Array.isArray(body), 'Expected array');
  });

  // --- POST /api/tasks ---
  await test('POST /api/tasks creates a task', async () => {
    const { status, body } = await fetchJSON('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title: '__test_task_' + Date.now(),
        priority: 'medium',
      }),
    });
    assert(status === 201, `Expected 201, got ${status}`);
    assert(body.entity_id !== undefined, 'Missing entity_id in response');
  });

  // --- POST /api/law/refresh ---
  await test('POST /api/law/refresh records timestamp', async () => {
    const { status, body } = await fetchJSON('/api/law/refresh', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    assert(status === 200, `Expected 200, got ${status}`);
    assert(body.success === true, 'Expected success: true');
    assert(typeof body.refresh_requested_at === 'number', 'Missing refresh_requested_at');
  });

  // --- POST /api/law/acknowledge ---
  await test('POST /api/law/acknowledge works', async () => {
    const { status, body } = await fetchJSON('/api/law/acknowledge', {
      method: 'POST',
      body: JSON.stringify({ order: 'CLOSURE: Close loops' }),
    });
    assert(status === 200, `Expected 200, got ${status}`);
    assert(body.success === true, 'Expected success: true');
  });

  // --- POST /api/law/violation requires action ---
  await test('POST /api/law/violation rejects missing action', async () => {
    const { status, body } = await fetchJSON('/api/law/violation', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    assert(status === 400, `Expected 400, got ${status}`);
    assert(body.error !== undefined, 'Expected error message');
  });

  // Summary
  console.log('');
  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  console.log(`=== Results: ${passed} passed, ${failed} failed ===`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests().catch(err => {
  console.error('Test runner failed:', err);
  process.exit(1);
});
