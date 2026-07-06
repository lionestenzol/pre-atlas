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

// Bearer token for /api/* — fetched once from the exempt /api/auth/token endpoint.
// Stays null in dev mode (no .aegis-tenant-key); the server's auth middleware also
// bypasses auth in that case, so unauthenticated requests still pass.
let AUTH_TOKEN: string | null = null;

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
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (AUTH_TOKEN) {
    headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });
  const body = await res.json();
  return { status: res.status, body };
}

// ============================================================
// Tests
// ============================================================

async function runTests(): Promise<void> {
  console.log('=== Delta-Kernel API Tests ===\n');

  // Wait for server to be available, and fetch the auth token in the same probe.
  // /api/auth/token is exempt from the Bearer gate (see auth middleware in
  // src/api/server.ts) and returns the API key, or null in dev mode.
  let serverReady = false;
  for (let i = 0; i < 10; i++) {
    try {
      const res = await fetch(`${BASE}/api/auth/token`);
      const body = await res.json();
      AUTH_TOKEN = body?.token ?? null;
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
  // Contract: handler responds res.json({ id, title, status, priority, createdAt })
  // — status 200, field `id` (matches GET /api/tasks and the rest of the surface).
  await test('POST /api/tasks creates a task', async () => {
    const { status, body } = await fetchJSON('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title: '__test_task_' + Date.now(),
        priority: 'medium',
      }),
    });
    assert(status === 200, `Expected 200, got ${status}`);
    assert(body.id !== undefined, 'Missing id in response');
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

  // --- Pending-action confirmation gate ---
  // Governance daemon's Phase 3C wiring (governance_daemon.ts:826) is the real
  // caller; these tests exercise the HTTP surface it and /approve (openclaw)
  // both go through. action_type 'rest_action' is used deliberately — it has
  // no ACTION_TOKEN_MAP entry (executor-bridge.ts), so bridgeAction resolves
  // to { executed: false, status: 'skipped' } with no side effects on any
  // live channel (no message sent, no draft touched) *when* the mode gate
  // lets it through. ACTION_MODE_MAP restricts 'rest_action' to RECOVER mode
  // (cockpit.ts:128) — the confirm route re-checks mode at confirm time, not
  // just at creation, so this test branches on the live mode instead of
  // assuming one. Confirmed empirically: this run was in CLOSURE and the gate
  // correctly returned 403 rather than executing.
  let pendingActionId: string | undefined;
  let liveMode: string | undefined;

  await test('POST /api/actions/pending creates a pending action', async () => {
    const { status, body } = await fetchJSON('/api/actions/pending', {
      method: 'POST',
      body: JSON.stringify({
        action_type: 'rest_action',
        target_entity_id: '__test_target_' + Date.now(),
        payload: { label: 'api-test pending action' },
      }),
    });
    assert(status === 200, `Expected 200, got ${status}`);
    assert(body.id !== undefined, 'Missing id in response');
    assert(body.status === 'PENDING', `Expected status PENDING, got ${body.status}`);
    assert(typeof body.expires_at === 'number', 'Missing expires_at');
    pendingActionId = body.id;
  });

  await test('GET /api/actions/pending includes the created action', async () => {
    assert(pendingActionId !== undefined, 'No pendingActionId from create step');
    const { status, body } = await fetchJSON('/api/actions/pending');
    assert(status === 200, `Expected 200, got ${status}`);
    const found = (body.pending_actions as Array<{ id: string }>).find(a => a.id === pendingActionId);
    assert(found !== undefined, `Created action ${pendingActionId} not in pending list`);
  });

  await test('POST /api/actions/confirm/:id respects the live mode gate', async () => {
    assert(pendingActionId !== undefined, 'No pendingActionId from create step');
    const { body: stateBody } = await fetchJSON('/api/state/unified');
    liveMode = stateBody.derived.mode;

    const { status, body } = await fetchJSON(`/api/actions/confirm/${pendingActionId}`, {
      method: 'POST',
    });

    if (liveMode === 'RECOVER') {
      assert(status === 200, `Expected 200 in RECOVER mode, got ${status}`);
      assert(body.status === 'CONFIRMED', `Expected status CONFIRMED, got ${body.status}`);
      assert(body.execution !== undefined, 'Missing execution block');
      assert(body.execution.status === 'skipped', `Expected execution.status skipped (rest_action), got ${body.execution.status}`);
    } else {
      // rest_action is RECOVER-only (cockpit.ts ACTION_MODE_MAP) — outside
      // RECOVER the mode gate must block execution, not silently allow it.
      assert(status === 403, `Expected 403 outside RECOVER (mode: ${liveMode}), got ${status}`);
      assert(body.error !== undefined, 'Expected error message');
      assert(body.mode === liveMode, `Expected error body to echo mode ${liveMode}, got ${body.mode}`);
    }
  });

  await test('POST /api/actions/confirm/:id second call matches first outcome', async () => {
    assert(pendingActionId !== undefined, 'No pendingActionId from create step');
    const { status, body } = await fetchJSON(`/api/actions/confirm/${pendingActionId}`, {
      method: 'POST',
    });
    if (liveMode === 'RECOVER') {
      // Already CONFIRMED by the prior test.
      assert(status === 409, `Expected 409 (already confirmed), got ${status}`);
    } else {
      // Still PENDING — the mode gate blocks every retry the same way.
      assert(status === 403, `Expected 403 (still gated), got ${status}`);
    }
    assert(body.error !== undefined, 'Expected error message');
  });

  await test('POST /api/actions/confirm/:id 404s for an unknown id', async () => {
    const { status, body } = await fetchJSON('/api/actions/confirm/__does_not_exist__', {
      method: 'POST',
    });
    assert(status === 404, `Expected 404, got ${status}`);
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
