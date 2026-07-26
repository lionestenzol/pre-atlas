import { describe, it, expect } from 'vitest';
import { compressTree, type SourceFile } from './compressor.js';
import { pruneMap } from './prune.js';
import { renderFlueMarkdown } from './flue.js';

const files: SourceFile[] = [
  { path: 'src/auth/login.ts', content: 'export function login() {}\n' },
  { path: 'src/auth/session.ts', content: 'export const SESSION = 1;\n' },
  { path: 'src/billing/invoice.ts', content: 'export class Invoice {}\n' },
];
const map = compressTree('repo://app', files);

describe('renderFlueMarkdown (compressed map)', () => {
  it('renders a header, stats line, and a section per file', () => {
    const md = renderFlueMarkdown(map);
    expect(md).toContain('# Delta SCP map · repo://app');
    expect(md).toContain('## Files');
    expect(md).toContain('### src/auth/login.ts');
    expect(md).toContain('`function login`');
    expect(md.endsWith('\n')).toBe(true);
  });
});

describe('renderFlueMarkdown (pruned map)', () => {
  const pruned = pruneMap(map, { paths: ['src/auth/login.ts'] });

  it('renders focus-first with anchor/neighbour detail and a collapsed context list', () => {
    const md = renderFlueMarkdown(pruned);
    expect(md).toContain('# Delta SCP focus · repo://app');
    expect(md).toContain('anchored: **true**');
    expect(md).toContain('## Focus');
    expect(md).toContain('## Context (collapsed)');
    // anchored file appears in Focus with its symbols
    expect(md).toContain('src/auth/login.ts');
    expect(md).toContain('_(anchor, typescript)_');
    // collapsed context file appears only as a stub line with its symbol count
    expect(md).toContain('`src/billing/invoice.ts` (typescript, 1 sym)');
  });

  it('is deterministic for identical input', () => {
    expect(renderFlueMarkdown(pruned)).toBe(renderFlueMarkdown(pruned));
  });
});
