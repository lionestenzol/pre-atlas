// Proves the tree-sitter extractor is wired through the compress pipeline and the
// graph builder — the end-to-end path, not just the treesitter unit.
import { describe, it, expect } from 'vitest';
import { compressTree, compressTreeAsync, type SourceFile } from './compressor.js';
import { buildGraphRows, buildGraphRowsAst } from './graph.js';

const C_FILE: SourceFile = {
  path: 'src/legacy.c',
  content: `struct Config { int flags; };

int helper(int x) { return x * 2; }

int run(int n) {
  return helper(n);
}
`,
};

const GEN_AT = '2020-01-01T00:00:00.000Z';

describe('pipeline wiring: extractor selection', () => {
  it("regex path leaves C files empty (the gap we're closing)", async () => {
    const regex = compressTree('repo', [C_FILE], GEN_AT);
    const cNode = regex.symbolic_nodes.find((n) => n.path === 'src/legacy.c');
    expect(cNode?.symbols).toEqual([]);
  });

  it("compressTreeAsync('regex') is byte-identical to compressTree", async () => {
    const sync = compressTree('repo', [C_FILE], GEN_AT);
    const asyncRegex = await compressTreeAsync('repo', [C_FILE], GEN_AT, 'regex');
    expect(JSON.stringify(asyncRegex)).toBe(JSON.stringify(sync));
  });

  it("compressTreeAsync('treesitter') fills C symbols the regex misses", async () => {
    const map = await compressTreeAsync('repo', [C_FILE], GEN_AT, 'treesitter');
    const cNode = map.symbolic_nodes.find((n) => n.path === 'src/legacy.c');
    const names = (cNode?.symbols ?? []).map((s) => s.name);
    expect(names).toContain('helper');
    expect(names).toContain('run');
    expect(names).toContain('Config'); // struct — regex has no C pattern at all
    // stats are populated and internally consistent (yield = raw - compressed).
    expect(map.stats.token_yield).toBe(map.stats.raw_tokens_est - map.stats.compressed_tokens_est);
  });
});

describe('pipeline wiring: graph builder', () => {
  it('regex graph has file+import nodes but NO call edges', async () => {
    const rows = buildGraphRows('repo', [C_FILE]);
    // regex: no C symbol nodes, so only the file node
    expect(rows.nodes.filter((n) => n.node_type === 'function')).toEqual([]);
    expect(rows.edges.filter((e) => e.edge_type === 'calls')).toEqual([]);
  });

  it('AST graph emits function nodes AND a real calls edge (run -> helper)', async () => {
    const rows = await buildGraphRowsAst('repo', [C_FILE]);
    const fnNames = rows.nodes.filter((n) => n.node_type === 'function').map((n) => n.name);
    expect(fnNames).toContain('helper');
    expect(fnNames).toContain('run');

    const calls = rows.edges.filter((e) => e.edge_type === 'calls');
    const runHelper = calls.find(
      (e) => e.source.name === 'run' && e.target.name === 'helper',
    );
    expect(runHelper).toBeTruthy();
    // Both endpoints anchored to the same file (intra-file resolution).
    expect(runHelper?.source.file_path).toBe('src/legacy.c');
    expect(runHelper?.target.file_path).toBe('src/legacy.c');
  });

  it('buildGraphRowsAst is deterministic', async () => {
    const a = await buildGraphRowsAst('repo', [C_FILE]);
    const b = await buildGraphRowsAst('repo', [C_FILE]);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });
});
