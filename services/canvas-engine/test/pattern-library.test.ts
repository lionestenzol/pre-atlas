// canvas-engine pattern-library · picker determinism + group routing

import { describe, it, expect } from 'vitest';
import {
  buildPatternRegistry,
  pickPattern,
  normalizeDetection,
} from '../src/pattern-library/index.js';
import type { Region } from '../src/adapter/v1-schema.js';

function region(over: Partial<Region> & { id: string; n: number }): Region {
  return {
    id: over.id,
    n: over.n,
    name: over.name ?? `Region ${over.n}`,
    layer: over.layer ?? 'ui',
    selector: over.selector,
    file: over.file,
    line: over.line,
    detection: over.detection,
    desc: over.desc,
    note: over.note,
    kind: over.kind,
    bounds: over.bounds,
    fetches: over.fetches,
  };
}

describe('normalizeDetection', () => {
  it('routes r12-cursor-pointer to clickable', () => {
    expect(normalizeDetection(region({ id: 'a', n: 1, detection: 'r12-cursor-pointer' }))).toBe(
      'clickable',
    );
  });
  it('routes r7-native-interactive to clickable', () => {
    expect(normalizeDetection(region({ id: 'a', n: 1, detection: 'r7-native-interactive' }))).toBe(
      'clickable',
    );
  });
  it('routes sem-h1..h6 to heading', () => {
    for (const h of ['sem-h1', 'sem-h2', 'sem-h3', 'sem-h4', 'sem-h5', 'sem-h6']) {
      expect(normalizeDetection(region({ id: 'a', n: 1, detection: h }))).toBe('heading');
    }
  });
  it('routes sem-header/footer/section/main/aside/nav to landmark', () => {
    for (const d of ['sem-header', 'sem-footer', 'sem-section', 'sem-main', 'sem-aside', 'sem-nav']) {
      expect(normalizeDetection(region({ id: 'a', n: 1, detection: d }))).toBe('landmark');
    }
  });
  it('routes pattern-repeat to list', () => {
    expect(normalizeDetection(region({ id: 'a', n: 1, detection: 'pattern-repeat' }))).toBe('list');
  });
  it('routes form detection to form', () => {
    expect(normalizeDetection(region({ id: 'a', n: 1, detection: 'form' }))).toBe('form');
  });
  it('routes card-heuristic to card', () => {
    expect(normalizeDetection(region({ id: 'a', n: 1, detection: 'card-heuristic' }))).toBe('card');
  });
  it('routes kind=card to card even if detection unknown', () => {
    expect(normalizeDetection(region({ id: 'a', n: 1, kind: 'card', detection: 'whatever' }))).toBe(
      'card',
    );
  });
  it('routes unknown to default', () => {
    expect(normalizeDetection(region({ id: 'a', n: 1, detection: 'something-novel' }))).toBe(
      'default',
    );
  });
});

describe('pickPattern', () => {
  const registry = buildPatternRegistry();

  it('clickable button-leaning region picks clickable/button', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'r7-native-interactive',
      bounds: { x: 0, y: 0, w: 120, h: 40 },
    });
    const { pattern, group } = pickPattern(r, registry);
    expect(group).toBe('clickable');
    expect(pattern.name).toBe('clickable/button');
  });

  it('cursor-pointer link-leaning region picks clickable/link', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'r12-cursor-pointer',
      // long name keeps clickable/pill out of "perfect match" territory
      name: 'Read more about our pricing tiers and enterprise plans',
      bounds: { x: 0, y: 0, w: 320, h: 24 },
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('clickable/link');
  });

  it('icon-sized interactive region picks clickable/icon-button', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'r11-icon-sized-interactive',
      bounds: { x: 0, y: 0, w: 32, h: 32 },
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('clickable/icon-button');
  });

  it('heading region picks heading/tagged', () => {
    const r = region({ id: 'a', n: 1, detection: 'sem-h2', name: 'About' });
    const { pattern, group } = pickPattern(r, registry);
    expect(group).toBe('heading');
    expect(pattern.name).toBe('heading/tagged');
  });

  it('header landmark picks landmark/header', () => {
    const r = region({ id: 'a', n: 1, detection: 'sem-header', name: 'Top' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('landmark/header');
  });

  it('footer landmark picks landmark/footer', () => {
    const r = region({ id: 'a', n: 1, detection: 'sem-footer', name: 'Bottom' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('landmark/footer');
  });

  it('list region with long name + tall bounds picks list/vertical (default)', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'pattern-repeat',
      name: 'A long descriptive list title that should not match tags',
      bounds: { x: 0, y: 0, w: 320, h: 400 },
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('list/vertical');
  });

  it('list region with wide bounds picks list/grid', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'pattern-repeat',
      name: 'Wide grid',
      bounds: { x: 0, y: 0, w: 900, h: 400 },
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('list/grid');
  });

  it('list region with short name picks list/tags', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'pattern-repeat',
      name: 'Filters',
      bounds: { x: 0, y: 0, w: 320, h: 40 },
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('list/tags');
  });

  it('form with neutral name picks form/stacked (default)', () => {
    const r = region({ id: 'a', n: 1, detection: 'form', name: 'Contact form' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('form/stacked');
  });

  it('form with "search" keyword picks form/inline', () => {
    const r = region({ id: 'a', n: 1, detection: 'form', name: 'Search bar' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('form/inline');
  });

  it('form with "subscribe" keyword picks form/newsletter', () => {
    const r = region({ id: 'a', n: 1, detection: 'form', name: 'Subscribe to our newsletter' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('form/newsletter');
  });

  it('card with long name picks card/content (default)', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'card-heuristic',
      name: 'A long card title that should not be treated as a stat',
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('card/content');
  });

  it('card with numeric-looking name picks card/stat', () => {
    const r = region({ id: 'a', n: 1, detection: 'card-heuristic', name: '42' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('card/stat');
  });

  it('card with fetches picks card/action', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'card-heuristic',
      name: 'A long card title that should not be treated as a stat',
      fetches: [{ method: 'GET', url: '/api/data', status: 200 }],
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('card/action');
  });

  it('clickable region with cta keyword + large bounds picks clickable/cta', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'r7-native-interactive',
      name: 'Subscribe to plan',
      bounds: { x: 0, y: 0, w: 240, h: 56 },
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('clickable/cta');
  });

  it('clickable region with short tag-like name picks clickable/pill', () => {
    const r = region({
      id: 'a',
      n: 1,
      detection: 'r12-cursor-pointer',
      name: 'Active',
      bounds: { x: 0, y: 0, w: 70, h: 28 },
    });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('clickable/pill');
  });

  it('h1 region picks heading/hero', () => {
    const r = region({ id: 'a', n: 1, detection: 'sem-h1', name: 'Welcome' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('heading/hero');
  });

  it('h2 with desc picks heading/eyebrow', () => {
    const r = region({ id: 'a', n: 1, detection: 'sem-h2', name: 'Pricing', desc: 'plans' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('heading/eyebrow');
  });

  it('sem-nav picks landmark/nav', () => {
    const r = region({ id: 'a', n: 1, detection: 'sem-nav', name: 'Top nav' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('landmark/nav');
  });

  it('sem-aside picks landmark/aside', () => {
    const r = region({ id: 'a', n: 1, detection: 'sem-aside', name: 'Sidebar' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('landmark/aside');
  });

  it('unknown detection falls back to default/card', () => {
    const r = region({ id: 'a', n: 1, detection: 'novel-thing', name: 'Mystery' });
    const { pattern } = pickPattern(r, registry);
    expect(pattern.name).toBe('default/card');
  });
});

describe('pattern.render · output sanity', () => {
  const registry = buildPatternRegistry();

  it('every pattern produces a default-exported component named componentName', () => {
    const cases = [
      { detection: 'r7-native-interactive', expected: 'clickable/button' },
      { detection: 'r11-icon-sized-interactive', expected: 'clickable/icon-button' },
      { detection: 'r12-cursor-pointer', expected: 'clickable/link' },
      { detection: 'sem-h2', expected: 'heading/tagged' },
      { detection: 'sem-header', expected: 'landmark/header' },
      { detection: 'sem-footer', expected: 'landmark/footer' },
      { detection: 'sem-section', expected: 'landmark/section' },
      // Note: with multi-variant groups, "expected" is whichever variant wins
      // for a generic fixture (long name, no bounds, no fetches, plain detection).
      // Specific variants are covered by the dedicated pickPattern tests above.
      { detection: 'pattern-repeat', expected: 'list/vertical' },
      { detection: 'card-heuristic', expected: 'card/content' },
      { detection: 'form', expected: 'form/stacked' },
      { detection: 'novel', expected: 'default/card' },
    ];
    // Use a long name + tall bounds so generic variants win and short-name /
    // small-bounds variants score lower (e.g. list/tags, card/stat).
    const longName = 'A long descriptive sample title that should not match short-name variants';
    const tallBounds = { x: 0, y: 0, w: 320, h: 200 };
    for (const c of cases) {
      const r = region({
        id: 'x',
        n: 1,
        detection: c.detection,
        name: longName,
        bounds: tallBounds,
      });
      const { pattern } = pickPattern(r, registry);
      expect(pattern.name).toBe(c.expected);
      const out = pattern.render({ componentName: 'Sample', region: r, chains: [] });
      expect(out).toContain('export default function Sample()');
      expect(out.length).toBeGreaterThan(40);
    }
  });

  it('render output is deterministic (same input → same output)', () => {
    const r = region({ id: 'x', n: 7, detection: 'sem-h2', name: 'Pricing' });
    const { pattern } = pickPattern(r, registry);
    const a = pattern.render({ componentName: 'Pricing', region: r, chains: [] });
    const b = pattern.render({ componentName: 'Pricing', region: r, chains: [] });
    expect(a).toBe(b);
  });
});
