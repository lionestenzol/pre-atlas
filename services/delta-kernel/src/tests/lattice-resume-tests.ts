import * as assert from 'assert';
import * as os from 'os';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { isLatticeResumeJob, buildResumeArgs, resolveLatticePython } from '../governance/lattice_resume.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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

function runTests(): void {
  console.log('=== LangGraph Skill Lattice Seq 7 (Supervisor) Tests ===\n');

  test('isLatticeResumeJob is true only for metadata.kind === "lattice_resume"', () => {
    assert.strictEqual(isLatticeResumeJob({ job_id: 'j1', metadata: { kind: 'lattice_resume' } }), true);
    assert.strictEqual(isLatticeResumeJob({ job_id: 'j2', metadata: { kind: 'something_else' } }), false);
    assert.strictEqual(isLatticeResumeJob({ job_id: 'j3', metadata: {} }), false);
    assert.strictEqual(isLatticeResumeJob({ job_id: 'j4', metadata: { cmd: 'echo hi' } }), false);
  });

  test('buildResumeArgs throws when thread_id or db is missing (cannot resume without them)', () => {
    assert.throws(() => buildResumeArgs('j1', { kind: 'lattice_resume' }), /missing thread_id\/db/);
    assert.throws(() => buildResumeArgs('j1', { kind: 'lattice_resume', thread_id: 't1' }), /missing thread_id\/db/);
    assert.doesNotThrow(() => buildResumeArgs('j1', { kind: 'lattice_resume', thread_id: 't1', db: 'x.sqlite' }));
  });

  test('buildResumeArgs always passes --resume, --job-id, and --supervised for a real chain', () => {
    const args = buildResumeArgs('job-42', {
      kind: 'lattice_resume',
      thread_id: 't1',
      db: 'lattice_runs.sqlite',
      pairs: [['code-recon', 'find X']],
    });

    assert.strictEqual(args[0], 'run_chain.py');
    assert.ok(args.includes('--thread-id'));
    assert.strictEqual(args[args.indexOf('--thread-id') + 1], 't1');
    assert.ok(args.includes('--resume'), 'Must pass --resume so LangGraph resumes instead of restarting');
    assert.ok(args.includes('--db'));
    assert.strictEqual(args[args.indexOf('--db') + 1], 'lattice_runs.sqlite');
    assert.ok(args.includes('--job-id'), 'Must pass the SAME job_id, not register a new one');
    assert.strictEqual(args[args.indexOf('--job-id') + 1], 'job-42');
    assert.ok(args.includes('--supervised'));
    assert.ok(args.includes('code-recon'), 'Must replay the same skill/prompt pairs so the graph shape matches');
    assert.ok(args.includes('find X'));
    assert.ok(!args.includes('--demo'), 'A real (non-demo) job must not get --demo tacked on');
  });

  test('buildResumeArgs passes --demo instead of skill/prompt pairs for a demo job', () => {
    const args = buildResumeArgs('job-7', {
      kind: 'lattice_resume',
      thread_id: 't-demo',
      db: 'viewer_runs.sqlite',
      demo: true,
      pairs: [['code-recon', 'should be ignored for a demo job']],
    });

    assert.ok(args.includes('--demo'));
    assert.ok(!args.includes('code-recon'), 'demo=true must not also replay real pairs');
    assert.ok(!args.includes('should be ignored for a demo job'));
  });

  test('buildResumeArgs forwards max_turns/max_budget_usd only when set', () => {
    const withBudget = buildResumeArgs('j1', {
      kind: 'lattice_resume', thread_id: 't1', db: 'x.sqlite', demo: true,
      max_turns: 5, max_budget_usd: 1.5,
    });
    assert.ok(withBudget.includes('--max-turns'));
    assert.strictEqual(withBudget[withBudget.indexOf('--max-turns') + 1], '5');
    assert.ok(withBudget.includes('--max-budget'));
    assert.strictEqual(withBudget[withBudget.indexOf('--max-budget') + 1], '1.5');

    const withoutBudget = buildResumeArgs('j1', { kind: 'lattice_resume', thread_id: 't1', db: 'x.sqlite', demo: true });
    assert.ok(!withoutBudget.includes('--max-turns'));
    assert.ok(!withoutBudget.includes('--max-budget'));
  });

  test('resolveLatticePython falls back to bare "python" when the venv is absent', () => {
    // A repoRoot with no services/atlas-map-api/.venv -- os.tmpdir() is guaranteed
    // not to contain that tree.
    const fallback = resolveLatticePython(os.tmpdir());
    assert.strictEqual(fallback, 'python');
  });

  test('resolveLatticePython picks the isolated venv when it exists (real repo root)', () => {
    // services/delta-kernel/src/tests -> repo root is 4 levels up. This venv is
    // where Seq 3 installed langgraph specifically because the global Python
    // has an incompatible langchain-core pin (tools/lattice/README.md).
    const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');
    const resolved = resolveLatticePython(repoRoot);
    assert.ok(resolved.includes('.venv'), `Expected the isolated venv to be picked, got: ${resolved}`);
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
