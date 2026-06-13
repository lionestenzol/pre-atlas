import { describe, it, expect } from 'vitest';
import {
  compressTree,
  estimateTokens,
  extractSymbols,
  languageForPath,
} from './compressor.js';

describe('languageForPath', () => {
  it('maps known extensions', () => {
    expect(languageForPath('src/foo.ts')).toBe('typescript');
    expect(languageForPath('a/b/c.py')).toBe('python');
    expect(languageForPath('main.go')).toBe('go');
  });
  it('falls back to "other" for unknown extensions', () => {
    expect(languageForPath('image.png')).toBe('other');
    expect(languageForPath('NOEXT')).toBe('other');
  });
});

describe('estimateTokens', () => {
  it('approximates ~4 chars per token', () => {
    expect(estimateTokens('')).toBe(0);
    expect(estimateTokens('abcd')).toBe(1);
    expect(estimateTokens('abcde')).toBe(2);
  });
});

describe('extractSymbols', () => {
  it('extracts TS functions, classes, interfaces, exports with line numbers', () => {
    const src = [
      'export function alpha() {}', // 1
      'class Beta {}', // 2
      'export const gamma = 3;', // 3
      'interface Delta {}', // 4
    ].join('\n');
    const syms = extractSymbols(src, 'typescript');
    expect(syms).toEqual([
      { kind: 'function', name: 'alpha', line: 1 },
      { kind: 'class', name: 'Beta', line: 2 },
      { kind: 'const', name: 'gamma', line: 3 },
      { kind: 'interface', name: 'Delta', line: 4 },
    ]);
  });

  it('extracts python def/class', () => {
    const src = 'class Foo:\n    def bar(self):\n        pass\n';
    expect(extractSymbols(src, 'python')).toEqual([
      { kind: 'class', name: 'Foo', line: 1 },
      { kind: 'def', name: 'bar', line: 2 },
    ]);
  });

  it('returns nothing for languages without patterns', () => {
    expect(extractSymbols('# title', 'markdown')).toEqual([]);
  });
});

describe('compressTree', () => {
  const files = [
    { path: 'b.ts', content: 'export function b() {}\n' },
    { path: 'a.py', content: 'def a():\n    return 1\n' },
  ];

  it('produces a DELTA_SCP envelope with deterministic, sorted nodes', () => {
    const out = compressTree('repo://x', files);
    expect(out.protocol).toBe('DELTA_SCP');
    expect(out.status).toBe('compressed');
    expect(out.repo).toBe('repo://x');
    expect(out.symbolic_nodes.map((n) => n.path)).toEqual(['a.py', 'b.ts']);
    expect(out.languages).toEqual({ python: 1, typescript: 1 });
  });

  it('reports stats with a positive token yield on real source', () => {
    // Realistic source: a symbol declaration followed by non-symbol body lines,
    // which is where structural compression actually pays off.
    const block = (i: number) =>
      `export function fn${i}(input: string): string {\n` +
      '  const trimmed = input.trim();\n' +
      '  const upper = trimmed.toUpperCase();\n' +
      '  // perform the transformation and return the result\n' +
      '  return upper + trimmed.length.toString();\n' +
      '}\n\n';
    const big = {
      path: 'big.ts',
      content: Array.from({ length: 200 }, (_, i) => block(i)).join(''),
    };
    const out = compressTree('repo://x', [big]);
    expect(out.stats.files_included).toBe(1);
    expect(out.stats.raw_tokens_est).toBeGreaterThan(out.stats.compressed_tokens_est);
    expect(out.stats.token_yield).toBe(
      out.stats.raw_tokens_est - out.stats.compressed_tokens_est,
    );
    expect(out.stats.compression_ratio).toBeGreaterThan(0);
    expect(out.stats.compression_ratio).toBeLessThan(1);
  });

  it('handles an empty repo without dividing by zero', () => {
    const out = compressTree('repo://empty', []);
    expect(out.stats.raw_tokens_est).toBe(0);
    expect(out.stats.compression_ratio).toBe(0);
    expect(out.symbolic_nodes).toEqual([]);
  });
});
