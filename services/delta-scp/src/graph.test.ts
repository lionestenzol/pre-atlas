import { describe, it, expect } from 'vitest';
import { buildGraphRows } from './graph.js';
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

  it('resolves a python dotted import to a repo file', () => {
    const e = edges.find((x) => x.source.file_path === 'src/app.py');
    expect(e?.target.file_path).toBe('auth/helpers.py');
  });

  it('is deterministic', () => {
    expect(buildGraphRows('app', files)).toEqual(buildGraphRows('app', files));
  });
});
