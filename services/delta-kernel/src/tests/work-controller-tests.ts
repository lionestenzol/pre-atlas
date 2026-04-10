import * as assert from 'assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { WorkController, WorkRequest } from '../core/work-controller.js';

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

const SYSTEM_STATE = {
  mode: 'BUILD',
  build_allowed: true,
  open_loops: 0,
  closure_ratio: 1,
} as const;

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

function withController(run: (controller: WorkController, rootDir: string) => void): void {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'delta-kernel-work-'));
  const sensorDir = path.join(rootDir, 'services', 'cognitive-sensor');
  fs.mkdirSync(sensorDir, { recursive: true });

  const previousSensorDir = process.env.COGNITIVE_SENSOR_DIR;
  process.env.COGNITIVE_SENSOR_DIR = sensorDir;

  try {
    const controller = new WorkController(rootDir);
    run(controller, rootDir);
  } finally {
    if (previousSensorDir === undefined) {
      delete process.env.COGNITIVE_SENSOR_DIR;
    } else {
      process.env.COGNITIVE_SENSOR_DIR = previousSensorDir;
    }
    fs.rmSync(rootDir, { recursive: true, force: true });
  }
}

function requestExecutableWork(controller: WorkController, timeoutMs: number): string {
  const request: WorkRequest = {
    type: 'ai',
    title: `test-${timeoutMs}`,
    timeout_ms: timeoutMs,
    metadata: {
      cmd: 'echo test',
    },
  };

  const response = controller.request(request, SYSTEM_STATE);
  assert.strictEqual(response.status, 'APPROVED');
  return response.job_id;
}

function getActiveJob(controller: WorkController, jobId: string): any {
  const job = controller.getJob(jobId);
  assert.ok(job, `Expected job ${jobId} to exist`);
  return job;
}

function runTests(): void {
  console.log('=== Work Controller Tests ===\n');

  test('request stores timeout_ms on active jobs and metadata', () => {
    withController(controller => {
      const jobId = requestExecutableWork(controller, 10_000);
      const job = getActiveJob(controller, jobId);

      assert.strictEqual(job.timeout_ms, 10_000);
      assert.strictEqual(job.metadata.timeout_ms, 10_000);
    });
  });

  test('claim uses job-specific timeout for claim TTL', () => {
    withController(controller => {
      requestExecutableWork(controller, 10_000);
      const beforeClaim = Date.now();
      const claim = controller.claimNextExecutable('executor-a');

      assert.strictEqual(claim.claimed, true);
      const execution = (claim.job?.metadata as any).execution;
      assert.ok(execution, 'Expected execution metadata on claimed job');

      const ttlMs = execution.claim_expires_at - execution.claimed_at;
      assert.ok(ttlMs >= 10_000 && ttlMs < 11_500, `Expected ~10000ms TTL, got ${ttlMs}`);
      assert.ok(execution.claimed_at >= beforeClaim, 'Claim timestamp should be current');
    });
  });

  test('claim enforces minimum TTL for very short jobs', () => {
    withController(controller => {
      requestExecutableWork(controller, 1);
      const claim = controller.claimNextExecutable('executor-short');

      assert.strictEqual(claim.claimed, true);
      const execution = (claim.job?.metadata as any).execution;
      const ttlMs = execution.claim_expires_at - execution.claimed_at;
      assert.ok(ttlMs >= 5_000, `Expected minimum TTL floor, got ${ttlMs}`);
    });
  });

  test('extendClaim requires the claiming executor and applies TTL floor', () => {
    withController(controller => {
      const jobId = requestExecutableWork(controller, 20_000);
      controller.claimNextExecutable('executor-owner');

      const denied = controller.extendClaim(jobId, 'executor-other', 1_000);
      assert.strictEqual(denied.extended, false);

      const extended = controller.extendClaim(jobId, 'executor-owner', 1_000);
      assert.strictEqual(extended.extended, true);
      assert.ok(extended.new_expires_at, 'Expected new expiration time');
      assert.ok((extended.new_expires_at as number) - Date.now() >= 4_500, 'Expected extension TTL floor');
    });
  });

  test('claim metrics track successes, misses, extensions, and observed expirations', () => {
    withController(controller => {
      const jobId = requestExecutableWork(controller, 8_000);
      const firstClaim = controller.claimNextExecutable('executor-1');
      assert.strictEqual(firstClaim.claimed, true);

      const secondClaim = controller.claimNextExecutable('executor-2');
      assert.strictEqual(secondClaim.claimed, false);

      const activeJob = getActiveJob(controller, jobId);
      activeJob.metadata.execution.claim_expires_at = Date.now() - 1_000;

      const reclaimed = controller.claimNextExecutable('executor-2');
      assert.strictEqual(reclaimed.claimed, true);

      const extended = controller.extendClaim(jobId, 'executor-2', 9_000);
      assert.strictEqual(extended.extended, true);

      const metrics = controller.getClaimMetrics();
      assert.strictEqual(metrics.totals.claims, 2);
      assert.strictEqual(metrics.totals.failed_claims, 1);
      assert.strictEqual(metrics.totals.extended_claims, 1);
      assert.strictEqual(metrics.totals.expired_claims, 1);
      assert.ok(metrics.average_claim_ttl_ms >= 5_000, 'Expected non-zero average TTL');
    });
  });

  console.log('');
  const passed = results.filter(result => result.passed).length;
  const failed = results.length - passed;
  console.log(`=== Results: ${passed} passed, ${failed} failed ===`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
