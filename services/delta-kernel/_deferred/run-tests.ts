/**
 * Delta-State Fabric v0 — Test Runner
 *
 * Run with: npx ts-node src/core/run-tests.ts
 * Or: npx tsx src/core/run-tests.ts
 */

import { runAllTests } from './fabric-tests';

async function main() {
  console.log('Starting Delta-State Fabric Proof Tests...\n');

  try {
    const { results, summary } = await runAllTests();

    // Exit with appropriate code
    process.exit(summary.failed > 0 ? 1 : 0);
  } catch (error) {
    console.error('Test runner failed:', error);
    process.exit(1);
  }
}

main();
