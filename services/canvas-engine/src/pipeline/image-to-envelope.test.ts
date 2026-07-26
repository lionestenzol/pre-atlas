// Offline verification of the IMAGE → ENVELOPE bridge's deterministic transform.
// No live LLM call: we feed a fixture "model output" string (the JSON the vision
// model would return) and assert it becomes a schema-valid AnatomyV1 envelope,
// that each role routes to the right pattern group, and that the envelope feeds
// the existing deterministic generator to a real React skeleton.

import { describe, it, expect } from 'vitest';

import { anatomyV1Schema } from '../adapter/v1-schema.js';
import { buildPatternRegistry, pickPattern } from '../pattern-library/index.js';
import { generateFromEnvelope } from './url-to-clone.js';
import { __test } from './image-to-envelope.js';

const { buildEnvelope, normalizeRole, extractJsonObject } = __test;

// A realistic model response: fenced JSON wrapped in prose, one region per role,
// an unknown role ("sparkle"), and one region with no bounds ("Email Field").
const MODEL_OUTPUT = `Here is the UI structure I extracted:
\`\`\`json
{
  "regions": [
    {"name":"Top Bar","role":"header","desc":"Site header","x":0,"y":0,"w":100,"h":8},
    {"name":"Primary Nav","role":"nav","desc":"Main navigation","x":0,"y":8,"w":100,"h":6},
    {"name":"Filters","role":"sidebar","desc":"Left filter rail","x":0,"y":14,"w":20,"h":80},
    {"name":"Hero Title","role":"heading","desc":"Page title","x":22,"y":16,"w":50,"h":8},
    {"name":"Get Started","role":"cta","desc":"Primary call to action","x":22,"y":26,"w":18,"h":6},
    {"name":"Learn More","role":"button","desc":"Secondary button","x":42,"y":26,"w":16,"h":6},
    {"name":"Search Form","role":"form","desc":"Search input group","x":22,"y":34,"w":50,"h":7},
    {"name":"Email Field","role":"input","desc":"Email input"},
    {"name":"Feature Cards","role":"list","desc":"Grid of features","x":22,"y":44,"w":50,"h":30},
    {"name":"Pricing Card","role":"card","desc":"A pricing tier","x":74,"y":44,"w":24,"h":30},
    {"name":"Hero Image","role":"image","desc":"Illustration","x":74,"y":16,"w":24,"h":24},
    {"name":"Body Copy","role":"text","desc":"Paragraph text","x":22,"y":76,"w":50,"h":10},
    {"name":"Mystery Widget","role":"sparkle","desc":"unknown role maps to text","x":0,"y":90,"w":100,"h":4},
    {"name":"Footer","role":"footer","desc":"Site footer","x":0,"y":94,"w":100,"h":6}
  ]
}
\`\`\`
That's the layout.`;

describe('image-to-envelope · extractJsonObject', () => {
  it('pulls JSON from a fenced block surrounded by prose', () => {
    const obj = extractJsonObject(
      'intro\n```json\n{"regions":[]}\n```\noutro',
    ) as { regions: unknown[] };
    expect(obj.regions).toEqual([]);
  });

  it('pulls a bare JSON object with trailing text', () => {
    const obj = extractJsonObject(
      '{"regions":[{"name":"x","role":"text"}]} cheers',
    ) as { regions: unknown[] };
    expect(obj.regions).toHaveLength(1);
  });

  it('throws when no JSON object is present', () => {
    expect(() => extractJsonObject('no json here')).toThrow();
  });
});

describe('image-to-envelope · normalizeRole', () => {
  it('passes through known roles (case / space insensitive)', () => {
    expect(normalizeRole('Button')).toBe('button');
    expect(normalizeRole('  HEADER ')).toBe('header');
  });

  it('maps unknown roles to text', () => {
    expect(normalizeRole('sparkle')).toBe('text');
  });
});

describe('image-to-envelope · buildEnvelope', () => {
  const env = buildEnvelope(MODEL_OUTPUT, 'unit-test', 'cli');

  it('produces a schema-valid anatomy-v1 envelope', () => {
    expect(anatomyV1Schema.safeParse(env).success).toBe(true);
    expect(env.version).toBe('anatomy-v1');
  });

  it('marks metadata as an image-sourced spa with all five layers', () => {
    expect(env.metadata.source).toBe('image');
    expect(env.metadata.mode).toBe('spa');
    expect(env.metadata.tools.length).toBeGreaterThanOrEqual(1);
    expect(Object.keys(env.layers).sort()).toEqual([
      'api',
      'ext',
      'lib',
      'state',
      'ui',
    ]);
  });

  it('carries no backend chains (not observable from a screenshot)', () => {
    expect(env.chains).toEqual([]);
  });

  it('numbers regions sequentially with unique ids, all ui layer', () => {
    expect(env.regions).toHaveLength(14);
    env.regions.forEach((r, i) => {
      expect(r.n).toBe(i + 1);
      expect(r.layer).toBe('ui');
    });
    const ids = new Set(env.regions.map((r) => r.id));
    expect(ids.size).toBe(env.regions.length);
  });

  it('preserves bounds when present and omits them when absent', () => {
    const header = env.regions.find((r) => r.name === 'Top Bar');
    expect(header?.bounds).toEqual({ x: 0, y: 0, w: 100, h: 8 });
    const email = env.regions.find((r) => r.name === 'Email Field');
    expect(email?.bounds).toBeUndefined();
  });
});

describe('image-to-envelope · role routing through pickPattern', () => {
  const env = buildEnvelope(MODEL_OUTPUT, 'unit-test', 'cli');
  const registry = buildPatternRegistry();
  const groupOf = (name: string): string => {
    const region = env.regions.find((r) => r.name === name);
    if (region === undefined) throw new Error(`region "${name}" not found`);
    return pickPattern(region, registry).group;
  };

  it('routes layout landmarks to the landmark group', () => {
    expect(groupOf('Top Bar')).toBe('landmark');
    expect(groupOf('Primary Nav')).toBe('landmark');
    expect(groupOf('Filters')).toBe('landmark');
    expect(groupOf('Footer')).toBe('landmark');
  });

  it('routes heading / clickable / form / list / card correctly', () => {
    expect(groupOf('Hero Title')).toBe('heading');
    expect(groupOf('Get Started')).toBe('clickable');
    expect(groupOf('Learn More')).toBe('clickable');
    expect(groupOf('Search Form')).toBe('form');
    expect(groupOf('Email Field')).toBe('form');
    expect(groupOf('Feature Cards')).toBe('list');
    expect(groupOf('Pricing Card')).toBe('card');
  });

  it('routes image / text / unknown-role to the default group', () => {
    expect(groupOf('Hero Image')).toBe('default');
    expect(groupOf('Body Copy')).toBe('default');
    expect(groupOf('Mystery Widget')).toBe('default');
  });
});

describe('image-to-envelope · feeds the deterministic generator', () => {
  const env = buildEnvelope(MODEL_OUTPUT, 'unit-test', 'cli');
  const files = generateFromEnvelope(env);

  it('emits an App.jsx entry and an index.css', () => {
    const paths = files.map((f) => f.path);
    expect(paths).toContain('src/App.jsx');
    expect(paths).toContain('src/index.css');
  });

  it('emits one component file per region', () => {
    const components = files.filter((f) =>
      f.path.startsWith('src/components/'),
    );
    expect(components).toHaveLength(env.regions.length);
  });

  it('App.jsx default-exports and imports its components', () => {
    const app = files.find((f) => f.path === 'src/App.jsx');
    expect(app?.content).toContain('export default function App()');
    expect(app?.content).toContain('import ');
  });
});
