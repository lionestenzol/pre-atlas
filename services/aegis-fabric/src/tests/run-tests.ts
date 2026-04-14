/**
 * Aegis Enterprise Fabric — Test Runner
 */

import { runDeltaTests } from './test-delta.js';
import { runPolicyTests } from './test-policy.js';
import { runAdapterTests } from './test-agent-adapter.js';
import { runApprovalTests } from './test-approval.js';
import { runSnapshotTests } from './test-snapshot.js';
import { runIntegrationTests } from './test-integration.js';

interface TestResult {
  name: string;
  passed: number;
  failed: number;
  errors: string[];
}

async function runSuite(name: string, fn: () => Promise<TestResult>): Promise<TestResult> {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`  ${name}`);
  console.log('='.repeat(60));
  try {
    const result = await fn();
    const status = result.failed === 0 ? 'PASS' : 'FAIL';
    console.log(`  [${status}] ${result.passed} passed, ${result.failed} failed`);
    for (const err of result.errors) {
      console.log(`    ERROR: ${err}`);
    }
    return result;
  } catch (err) {
    console.log(`  [CRASH] ${err}`);
    return { name, passed: 0, failed: 1, errors: [String(err)] };
  }
}

async function main() {
  console.log('\nAegis Enterprise Fabric — Test Suite\n');
  const start = Date.now();

  const results: TestResult[] = [];

  results.push(await runSuite('Delta Operations', runDeltaTests));
  results.push(await runSuite('Policy Engine', runPolicyTests));
  results.push(await runSuite('Agent Adapter', runAdapterTests));
  results.push(await runSuite('Approval Queue', runApprovalTests));
  results.push(await runSuite('Snapshot Manager', runSnapshotTests));
  results.push(await runSuite('Integration', runIntegrationTests));

  const total = results.reduce((acc, r) => ({ passed: acc.passed + r.passed, failed: acc.failed + r.failed }), { passed: 0, failed: 0 });
  const elapsed = Date.now() - start;

  console.log(`\n${'='.repeat(60)}`);
  console.log(`  TOTAL: ${total.passed} passed, ${total.failed} failed (${elapsed}ms)`);
  console.log('='.repeat(60));

  if (total.failed > 0) {
    process.exit(1);
  }
}

main().catch(err => {
  console.error('Test runner crashed:', err);
  process.exit(1);
});
