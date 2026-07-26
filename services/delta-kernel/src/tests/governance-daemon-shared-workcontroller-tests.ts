/**
 * Regression test for a real bug found live-testing LangGraph Skill Lattice
 * Seq 7 (Supervisor): server.ts and GovernanceDaemon each used to construct
 * their OWN `new WorkController(repoRoot)`. Both load the on-disk ledger once
 * at construction and never see each other's writes again -- a job
 * registered through /api/work/request (server.ts's instance) was invisible
 * to the daemon's checkTimeouts() (its own, separately-loaded, permanently
 * stale instance), so a timed-out job silently never retried. Fixed by
 * sharing one WorkController instance (governance_daemon.ts's constructor
 * now accepts one; server.ts passes its own). This test proves the daemon
 * actually uses the SHARED instance's checkTimeouts, not a fresh one.
 */
import * as assert from 'assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { WorkController, WorkRequest } from '../core/work-controller.js';
import { GovernanceDaemon } from '../governance/governance_daemon.js';
import { Storage } from '../cli/sqlite-storage.js';

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
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    results.push({ name, passed: false, error: message });
    console.log(`  [FAIL] ${name} — ${message}`);
  }
}

function withSharedController(
  run: (daemon: GovernanceDaemon, workController: WorkController) => Promise<void>,
): Promise<void> {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'delta-kernel-daemon-'));
  const sensorDir = path.join(rootDir, 'services', 'cognitive-sensor');
  fs.mkdirSync(sensorDir, { recursive: true });

  const previousSensorDir = process.env.COGNITIVE_SENSOR_DIR;
  process.env.COGNITIVE_SENSOR_DIR = sensorDir;

  const storage = new Storage({ dataDir: path.join(rootDir, 'data') });
  const workController = new WorkController(rootDir);
  const daemon = new GovernanceDaemon(storage, rootDir, workController);

  return run(daemon, workController).finally(() => {
    if (previousSensorDir === undefined) {
      delete process.env.COGNITIVE_SENSOR_DIR;
    } else {
      process.env.COGNITIVE_SENSOR_DIR = previousSensorDir;
    }
    storage.close();
    fs.rmSync(rootDir, { recursive: true, force: true });
  });
}

const SYSTEM_STATE = { mode: 'BUILD', build_allowed: true, open_loops: 0, closure_ratio: 1 } as const;

async function runTests(): Promise<void> {
  console.log('=== GovernanceDaemon Shared WorkController Tests ===\n');

  await withSharedController((daemon, workController) =>
    test('daemon.runJob("work_queue") calls checkTimeouts on the injected instance, not a fresh one', async () => {
      const calls: number[] = [];
      const original = workController.checkTimeouts.bind(workController);
      workController.checkTimeouts = () => {
        calls.push(Date.now());
        return original();
      };

      assert.strictEqual(calls.length, 0, 'Precondition: no calls yet');
      await daemon.runJob('work_queue');
      assert.strictEqual(calls.length, 1, 'runJob("work_queue") must invoke checkTimeouts exactly once on the SAME instance the test holds a reference to');
    }));

  await withSharedController((daemon, workController) =>
    test('a job registered on the shared instance is visible to the daemon\'s checkTimeouts and gets retried', async () => {
      const req: WorkRequest = {
        type: 'system',
        title: 'test-job-visible-to-daemon',
        timeout_ms: 5,
        metadata: { probe: true },
      };
      const response = workController.request(req, SYSTEM_STATE);
      assert.strictEqual(response.status, 'APPROVED');
      const jobId = (response as { job_id: string }).job_id;

      // Let the 5ms timeout actually elapse.
      await new Promise((r) => setTimeout(r, 30));

      await daemon.runJob('work_queue');

      const job = workController.getJob(jobId) as { metadata: Record<string, unknown> } | null;
      assert.ok(job, 'Job should still exist (retried in place, not lost)');
      assert.strictEqual(job!.metadata.retry_count, 1,
        'checkTimeouts() run through the daemon must see and retry a job registered on the SAME shared instance -- ' +
        'before the fix, the daemon\'s own separately-constructed WorkController never saw this job at all');
    }));

  console.log('');
  const passed = results.filter((r) => r.passed).length;
  const failed = results.length - passed;
  console.log(`=== Results: ${passed} passed, ${failed} failed ===`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
