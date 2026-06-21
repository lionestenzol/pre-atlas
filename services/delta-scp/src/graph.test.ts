import { describe, it, expect } from 'vitest';
import { buildGraphRows, resolveEdgeRows, type AstEdgeRow } from './graph.js';
import type { SourceFile } from './compressor.js';

const files: SourceFile[] = [
  {
    path: 'src/auth/login.ts',
    content: "import { SESSION } from './session';\nexport function login() {}\n",
  },
  { path: 'src/auth/session.ts', content: 'export const SESSION = 1;\n' },
  { path: 'src/app.py', content: 'from auth.helpers import boot\nclass App:\n    def run(self):\n        pass\n' },
  { path: 'auth/helpers.py', content: 'def boot():\n    return 1\n' },
];

describe('buildGraphRows', () => {
  const { nodes, edges } = buildGraphRows('app', files);

  it('emits a file node per file plus a node per extracted symbol', () => {
    const fileNodes = nodes.filter((n) => n.node_type === 'file');
    expect(fileNodes.map((n) => n.file_path).sort()).toEqual([
      'auth/helpers.py',
      'src/app.py',
      'src/auth/login.ts',
      'src/auth/session.ts',
    ]);
    // login.ts contributes a function symbol node
    const login = nodes.find((n) => n.name === 'login');
    expect(login).toMatchObject({ node_type: 'function', file_path: 'src/auth/login.ts', start_line: 2 });
    expect(login?.raw_signature).toContain('export function login');
  });

  it('maps extractor kinds onto the schema enum', () => {
    expect(nodes.find((n) => n.name === 'App')?.node_type).toBe('class');
    expect(nodes.find((n) => n.name === 'SESSION')?.node_type).toBe('variable');
  });

  it('checksums file content and records language metadata', () => {
    const f = nodes.find((n) => n.node_type === 'file' && n.file_path === 'src/auth/session.ts')!;
    expect(f.checksum).toMatch(/^[0-9a-f]{64}$/);
    expect(f.metadata).toMatchObject({ language: 'typescript' });
  });

  it('resolves a relative TS import to a repo file as an imports edge', () => {
    const e = edges.find((x) => x.source.file_path === 'src/auth/login.ts');
    expect(e).toMatchObject({
      target: { file_path: 'src/auth/session.ts', node_type: 'file' },
      edge_type: 'imports',
    });
  });

  it('resolves a TS-ESM .js specifier to the .ts source file', () => {
    // import './session.js' must map to session.ts on disk, or every TS-ESM
    // import edge silently drops (the bug the live e2e caught).
    const esm = buildGraphRows('app', [
      { path: 'src/auth/login.ts', content: "import { SESSION } from './session.js';\n" },
      { path: 'src/auth/session.ts', content: 'export const SESSION = 1;\n' },
    ]);
    const e = esm.edges.find((x) => x.source.file_path === 'src/auth/login.ts');
    expect(e?.target.file_path).toBe('src/auth/session.ts');
  });

  it('resolves a python dotted import to a repo file', () => {
    const e = edges.find((x) => x.source.file_path === 'src/app.py');
    expect(e?.target.file_path).toBe('auth/helpers.py');
  });

  it('is deterministic', () => {
    expect(buildGraphRows('app', files)).toEqual(buildGraphRows('app', files));
  });

  it('de-dups nodes sharing an identity so a plain insert stays unique-safe', () => {
    // Two defs with the same name+kind in one file (overload / conditional def).
    const dup = buildGraphRows('app', [
      { path: 'm.py', content: 'def foo():\n    pass\ndef foo():\n    pass\n' },
    ]);
    const fooNodes = dup.nodes.filter((n) => n.name === 'foo' && n.node_type === 'function');
    expect(fooNodes).toHaveLength(1);
    expect(fooNodes[0].start_line).toBe(1); // first occurrence wins
  });
});

describe('resolveEdgeRows', () => {
  const idByKey = new Map<string, string>([
    ['src/b/index.ts|index.ts|file', 'id-b'],
    ['src/c/index.ts|index.ts|file', 'id-c'],
    ['src/a.ts|a.ts|file', 'id-a'],
  ]);
  const edge = (sp: string, tp: string): AstEdgeRow => ({
    source: { file_path: sp, name: sp.split('/').pop()!, node_type: 'file' },
    target: { file_path: tp, name: tp.split('/').pop()!, node_type: 'file' },
    edge_type: 'imports',
    weight: 1,
  });

  it('resolves by full identity — same basename in different dirs does not collide', () => {
    const out = resolveEdgeRows([edge('src/a.ts', 'src/b/index.ts')], idByKey);
    expect(out).toEqual([{ source_id: 'id-a', target_id: 'id-b', edge_type: 'imports', weight: 1 }]);
    // a -> c/index.ts must map to id-c, NOT id-b, despite the identical basename
    const out2 = resolveEdgeRows([edge('src/a.ts', 'src/c/index.ts')], idByKey);
    expect(out2[0].target_id).toBe('id-c');
  });

  it('drops edges whose endpoints are not indexed (external/unindexed)', () => {
    const out = resolveEdgeRows([edge('src/a.ts', 'node_modules/x/index.ts')], idByKey);
    expect(out).toEqual([]);
  });
});
