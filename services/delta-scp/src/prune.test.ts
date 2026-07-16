import { describe, it, expect } from 'vitest';
import { compressTree, type SourceFile } from './compressor.js';
import { pruneMap, extractTracePaths } from './prune.js';

const repoFiles: SourceFile[] = [
  { path: 'src/auth/login.ts', content: 'export function login() {}\nexport function logout() {}\n' },
  { path: 'src/auth/session.ts', content: 'export const SESSION = 1;\n' },
  { path: 'src/billing/invoice.ts', content: 'export class Invoice {}\n' },
  { path: 'src/util/log.ts', content: 'export function log() {}\n' },
];

const map = compressTree('repo://app', repoFiles);

describe('extractTracePaths', () => {
  it('pulls source paths out of a raw stack trace, normalizing separators', () => {
    const trace = 'TypeError at src\\auth\\login.ts:12:5\n  called from src/util/log.ts:3';
    expect(extractTracePaths(trace).sort()).toEqual(['src/auth/login.ts', 'src/util/log.ts']);
  });
  it('returns nothing when no source paths are present', () => {
    expect(extractTracePaths('some generic error message')).toEqual([]);
  });
});

describe('pruneMap', () => {
  it('anchors an explicit path, keeps its dir siblings as neighbours, collapses the rest', () => {
    const out = pruneMap(map, { paths: ['src/auth/login.ts'] });
    expect(out.status).toBe('pruned');
    expect(out.stats.anchored).toBe(true);

    const byPath = Object.fromEntries(out.symbolic_nodes.map((n) => [n.path, n]));
    expect(byPath['src/auth/login.ts'].tier).toBe('anchor');
    expect(byPath['src/auth/session.ts'].tier).toBe('neighbor'); // same dir
    expect(byPath['src/billing/invoice.ts'].tier).toBe('context');
    expect(byPath['src/util/log.ts'].tier).toBe('context');
  });

  it('keeps symbols for anchor + neighbour, drops them for collapsed context', () => {
    const out = pruneMap(map, { paths: ['src/auth/login.ts'] });
    const byPath = Object.fromEntries(out.symbolic_nodes.map((n) => [n.path, n]));
    expect(byPath['src/auth/login.ts'].symbols.length).toBeGreaterThan(0);
    expect(byPath['src/auth/session.ts'].symbols.length).toBeGreaterThan(0);
    // context node collapsed: symbols dropped but count preserved
    expect(byPath['src/billing/invoice.ts'].collapsed).toBe(true);
    expect(byPath['src/billing/invoice.ts'].symbols).toEqual([]);
    expect(byPath['src/billing/invoice.ts'].symbol_count).toBe(1);
  });

  it('resolves anchors from a trace', () => {
    const out = pruneMap(map, { trace: 'boom at src/billing/invoice.ts:1' });
    expect(out.anchor.paths).toContain('src/billing/invoice.ts');
    const inv = out.symbolic_nodes.find((n) => n.path === 'src/billing/invoice.ts')!;
    expect(inv.tier).toBe('anchor');
    // focus_yield is always (before - after) by construction, regardless of sign
    expect(out.stats.focus_yield).toBe(out.stats.tokens_before - out.stats.tokens_after);
  });

  it('reduces token footprint when context dominates (realistic corpus)', () => {
    // Like compressor.test.ts' yield test: collapse only pays off once there is
    // real boilerplate to drop. Many symbol-heavy context files, one anchor.
    const big = compressTree('repo://big', [
      { path: 'src/auth/login.ts', content: 'export function login() {}\n' },
      ...Array.from({ length: 40 }, (_, i) => ({
        path: `src/mod${i}/file${i}.ts`,
        content: Array.from({ length: 10 }, (_, j) => `export function fn${i}_${j}() {}\n`).join(''),
      })),
    ]);
    const out = pruneMap(big, { paths: ['src/auth/login.ts'] });
    expect(out.stats.anchored).toBe(true);
    expect(out.stats.context_nodes).toBeGreaterThan(30);
    expect(out.stats.tokens_after).toBeLessThan(out.stats.tokens_before);
    expect(out.stats.focus_ratio).toBeLessThan(1);
  });

  it('anchors by symbol name', () => {
    const out = pruneMap(map, { symbols: ['Invoice'] });
    const inv = out.symbolic_nodes.find((n) => n.path === 'src/billing/invoice.ts')!;
    expect(inv.tier).toBe('anchor');
  });

  it('matches a bare basename mentioned in a trace', () => {
    const out = pruneMap(map, { paths: ['login.ts'] });
    const node = out.symbolic_nodes.find((n) => n.path === 'src/auth/login.ts')!;
    expect(node.tier).toBe('anchor');
  });

  it('returns the map intact (no collapse) when nothing resolves to an anchor', () => {
    const out = pruneMap(map, { paths: ['does/not/exist.ts'] });
    expect(out.stats.anchored).toBe(false);
    for (const n of out.symbolic_nodes) {
      expect(n.collapsed).toBe(false);
      expect(n.tier).toBe('context');
    }
  });

  it('is deterministic', () => {
    expect(pruneMap(map, { paths: ['src/auth/login.ts'] })).toEqual(
      pruneMap(map, { paths: ['src/auth/login.ts'] }),
    );
  });
});
