/**
 * PKT-010 verification: AtlasArtifact.v1 schema fixtures.
 *
 * 11 fixtures (6 happy, 5 bad) compiled against contracts/schemas/AtlasArtifact.v1.json.
 * ajv setup mirrors signals-store.ts:14,54-55 — strict:false + addFormats —
 * so format: date-time is actually enforced. Fixture 11 is the canary for that wiring;
 * if addFormats is dropped, "yesterday" silently passes and the gate must catch it.
 *
 * Run with: npx tsx src/tests/atlas-artifact-schema-tests.ts
 */

import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import Ajv, { type ErrorObject, type ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const repoRoot = join(__dirname, '..', '..', '..', '..');
const schemaPath = join(repoRoot, 'contracts', 'schemas', 'AtlasArtifact.v1.json');
const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));

const ajv = new Ajv({ strict: false, allErrors: true });
addFormats(ajv);
const validate: ValidateFunction = ajv.compile(schema);

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

function errors(): ErrorObject[] {
  return validate.errors ?? [];
}

function errorBlob(): string {
  return JSON.stringify(errors());
}

function baseArtifact(): Record<string, unknown> {
  return {
    schema_version: '1.0',
    id: 'art_test',
    created_at: '2026-06-15T14:43:21.108Z',
    source_layer: 'claude_code',
    artifact_type: 'explanation',
    payload: { title: 'Test title' },
  };
}

function runTests(): void {
  console.log('=== PKT-010 AtlasArtifact.v1 schema tests ===\n');

  test('fixture 1: happy widget (worked example) -> valid', () => {
    const fixture = {
      schema_version: '1.0',
      id: 'art_8a4f9b6e68f3',
      created_at: '2026-06-15T14:43:21.108Z',
      source_layer: 'claude_code',
      artifact_type: 'widget',
      topic: {
        text: 'delta-kernel autoheal explainer',
        origin: 'inferred_from_prior_turn',
        raw_command: '/show',
      },
      session: {
        session_id: '0631e005-bb73-4e67-ab25-579cf1e0a4e5',
        turn_index: 14,
        model: 'claude-opus-4-7[1m]',
      },
      payload: {
        title: 'Delta-kernel dies and self-heals within 15 minutes',
        prose: 'Tool availability. The visualize MCP server enables widgets.',
        widgets: [
          {
            title: 'delta_kernel_autoheal_explainer',
            mode: 'svg',
            source: '<svg width="100%" viewBox="0 0 680 460" role="img"></svg>',
            loading_messages: ['Drawing the heartbeat', 'Sketching the bounce-back'],
          },
        ],
        paired_turn: {
          prior_user_message: 'the widgets are new though bc it used to be ascii',
          prior_assistant_message: 'Explained that the visualize MCP server enabled SVG widgets vs prior ASCII.',
          prior_turn_index: 13,
        },
      },
    };
    const ok = validate(fixture);
    assert(ok === true, `expected valid; errors=${errorBlob()}`);
  });

  test('fixture 2: happy explanation (prose + topic only, no widgets, no paired_turn) -> valid', () => {
    const fixture = {
      ...baseArtifact(),
      artifact_type: 'explanation',
      topic: { text: 'how /loop pacing works', origin: 'explicit_arg' },
      payload: {
        title: 'How /loop self-paces',
        prose: 'The loop picks delaySeconds based on the cache TTL and the kind of work being polled.',
      },
    };
    const ok = validate(fixture);
    assert(ok === true, `expected valid; errors=${errorBlob()}`);
  });

  test('fixture 3: happy recon (payload.data = arbitrary nested object) -> valid', () => {
    const fixture = {
      ...baseArtifact(),
      artifact_type: 'recon',
      payload: {
        title: 'code-recon: locate signals-store callers',
        data: {
          findings: [
            { file: 'services/delta-kernel/src/api/server.ts', line: 412, symbol: 'ingestSignal' },
            { file: 'services/delta-kernel/src/atlas/lattice-projection.ts', line: 88, symbol: 'listSignals' },
          ],
          methods_used: ['grep', 'tree-sitter'],
          confidence: 'high',
        },
      },
    };
    const ok = validate(fixture);
    assert(ok === true, `expected valid; errors=${errorBlob()}`);
  });

  test('fixture 4: happy anatomy_map (source_layer=site_pull) -> valid', () => {
    const fixture = {
      ...baseArtifact(),
      source_layer: 'site_pull',
      artifact_type: 'anatomy_map',
      payload: {
        title: 'Anatomy map: stripe.com/pricing',
        data: { url: 'https://stripe.com/pricing', regions: 12, depth: 4 },
      },
    };
    const ok = validate(fixture);
    assert(ok === true, `expected valid; errors=${errorBlob()}`);
  });

  test('fixture 5: happy widget with mode "html" -> valid', () => {
    const fixture = {
      ...baseArtifact(),
      artifact_type: 'widget',
      payload: {
        title: 'Interactive HTML widget',
        widgets: [
          {
            mode: 'html',
            source: '<div><button>Click</button></div>',
          },
        ],
      },
    };
    const ok = validate(fixture);
    assert(ok === true, `expected valid; errors=${errorBlob()}`);
  });

  test('fixture 6: happy artifact with lattice_binding {node_id} -> valid', () => {
    const fixture = {
      ...baseArtifact(),
      lattice_binding: { node_id: 'n42' },
    };
    const ok = validate(fixture);
    assert(ok === true, `expected valid; errors=${errorBlob()}`);
  });

  test('fixture 7: missing schema_version (required) -> invalid; errors mention schema_version', () => {
    const fixture: Record<string, unknown> = baseArtifact();
    delete fixture.schema_version;
    const ok = validate(fixture);
    assert(ok === false, 'expected invalid');
    const blob = errorBlob();
    assert(blob.includes('schema_version'), `expected schema_version in errors; got ${blob}`);
  });

  test('fixture 8: missing payload.title (required nested) -> invalid; errors mention title', () => {
    const fixture = {
      ...baseArtifact(),
      payload: { prose: 'no title here' },
    };
    const ok = validate(fixture);
    assert(ok === false, 'expected invalid');
    const blob = errorBlob();
    assert(blob.includes('title'), `expected title in errors; got ${blob}`);
  });

  test('fixture 9: bad artifact_type "poem" -> invalid; errors mention enum', () => {
    const fixture = { ...baseArtifact(), artifact_type: 'poem' };
    const ok = validate(fixture);
    assert(ok === false, 'expected invalid');
    const violated = errors().some((e) => e.keyword === 'enum' && e.instancePath.includes('artifact_type'));
    assert(violated, `expected enum violation on /artifact_type; got ${errorBlob()}`);
  });

  test('fixture 10: bad source_layer "drilbit" -> invalid; errors mention enum', () => {
    const fixture = { ...baseArtifact(), source_layer: 'drilbit' };
    const ok = validate(fixture);
    assert(ok === false, 'expected invalid');
    const violated = errors().some((e) => e.keyword === 'enum' && e.instancePath.includes('source_layer'));
    assert(violated, `expected enum violation on /source_layer; got ${errorBlob()}`);
  });

  test('fixture 11 (canary): malformed created_at "yesterday" -> invalid; errors mention date-time format', () => {
    const fixture = { ...baseArtifact(), created_at: 'yesterday' };
    const ok = validate(fixture);
    assert(ok === false, 'expected invalid — if this passes, addFormats(ajv) is missing');
    const violated = errors().some((e) => e.keyword === 'format' && (e.params as { format?: string })?.format === 'date-time');
    assert(violated, `expected format=date-time violation; got ${errorBlob()}`);
  });

  const passed = results.filter((r) => r.passed).length;
  const failed = results.length - passed;
  console.log(`\n=== ${passed}/${results.length} PASS, ${failed} FAIL ===`);
  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
