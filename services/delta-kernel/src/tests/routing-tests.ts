import * as assert from 'assert';
import { bucketOpenLoops, computeNextMode, bucketSignals } from '../core/routing.js';
import type { SystemStateData } from '../core/types.js';

/**
 * Regression coverage for the open_loops threshold mismatch between this
 * TS Markov router and the Python governor (services/cognitive-sensor/
 * atlas_config.py). At 10 open loops -- a count the Python governor treats
 * as healthy/BUILD-eligible (its own open_loops_caution threshold) -- this
 * engine's bucketOpenLoops used to return 'LOW' at counts >= 4, which fires
 * the GLOBAL_OVERRIDE and force-locks CLOSURE from ANY mode, regardless of
 * every other signal. atlas-ai state/next/directive (the Python chain)
 * reported BUILD while this daemon's own system_state entity recorded
 * CLOSURE for the same real-world loop count. Fixed by aligning the bucket
 * boundaries to atlas_config.py's ROUTING (caution=10, critical=20).
 */

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

const results: TestResult[] = [];

function test(name: string, fn: () => void): void {
  try {
    fn();
    results.push({ name, passed: true });
    console.log(`  [PASS] ${name}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    results.push({ name, passed: false, error: message });
    console.log(`  [FAIL] ${name} — ${message}`);
  }
}

function baseSignals(openLoops: number): SystemStateData['signals'] {
  return {
    sleep_hours: 8,
    open_loops: openLoops,
    assets_shipped: 0,
    deep_work_blocks: 0,
    money_delta: 0,
  };
}

function runTests(): void {
  console.log('Routing threshold-parity tests\n');

  test('10 open loops is HIGH bucket (Python caution boundary, BUILD-eligible)', () => {
    assert.strictEqual(bucketOpenLoops(10), 'HIGH');
  });

  test('20 open loops is OK bucket (Python critical boundary, MAINTENANCE not CLOSURE)', () => {
    assert.strictEqual(bucketOpenLoops(20), 'OK');
  });

  test('21 open loops is LOW bucket (past Python\'s open_loops_critical)', () => {
    assert.strictEqual(bucketOpenLoops(21), 'LOW');
  });

  test('10 open loops does not force-lock CLOSURE from BUILD via the global override', () => {
    const buckets = bucketSignals(baseSignals(10));
    const nextMode = computeNextMode('BUILD', buckets);
    assert.notStrictEqual(nextMode, 'CLOSURE', 'BUILD should not be knocked back to CLOSURE at 10 open loops');
  });

  test('CLOSURE can exit to BUILD at 10 open loops (matches governor\'s own healthy threshold)', () => {
    const buckets = bucketSignals(baseSignals(10));
    const nextMode = computeNextMode('CLOSURE', buckets);
    assert.strictEqual(nextMode, 'BUILD');
  });

  test('21 open loops still force-locks CLOSURE from any mode (override must still work)', () => {
    const buckets = bucketSignals(baseSignals(21));
    const nextMode = computeNextMode('BUILD', buckets);
    assert.strictEqual(nextMode, 'CLOSURE');
  });

  console.log('');
  const passed = results.filter((result) => result.passed).length;
  const failed = results.length - passed;
  console.log(`=== Results: ${passed} passed, ${failed} failed ===`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
