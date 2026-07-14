import { describe, it, expect } from 'vitest';
import { extractSymbols } from './compressor.js';
import {
  extractSymbolsAst,
  extractCallEdgesAst,
  supportsAst,
  astLanguages,
} from './treesitter.js';

const C_SRC = `#include <stdio.h>

struct Point { int x; int y; };

int add(int a, int b) {
  return a + b;
}

int compute(int n) {
  int r = add(n, 1);
  return r;
}

int main(void) {
  int total = compute(41);
  printf("%d", total);
  return 0;
}
`;

describe('tree-sitter AST extractor', () => {
  it('capability map advertises the legacy languages', () => {
    expect(supportsAst('c')).toBe(true);
    expect(supportsAst('python')).toBe(true);
    expect(astLanguages()).toContain('c');
  });

  it('extracts C symbols where the regex extractor returns NOTHING', async () => {
    // The current delta-scp has no 'c' patterns -> zero symbols. This is the gap.
    expect(extractSymbols(C_SRC, 'c')).toEqual([]);

    const syms = await extractSymbolsAst(C_SRC, 'c');
    const names = syms.map((s) => s.name);
    expect(names).toContain('add');
    expect(names).toContain('compute');
    expect(names).toContain('main');
    expect(names).toContain('Point'); // struct — regex would never see this
    // exact line numbers
    const main = syms.find((s) => s.name === 'main');
    expect(main?.kind).toBe('function');
    expect(main?.line).toBe(14);
  });

  it('extracts caller->callee call edges (the edge type regex cannot produce)', async () => {
    const edges = await extractCallEdgesAst(C_SRC, 'c');
    // compute() calls add(); main() calls compute(). printf is a call too.
    expect(edges).toContainEqual({ source: 'compute', target: 'add', type: 'calls' });
    expect(edges).toContainEqual({ source: 'main', target: 'compute', type: 'calls' });
    // calls at file scope are skipped (no enclosing function) — no bogus edges.
    expect(edges.every((e) => e.source && e.target)).toBe(true);
  });

  it('handles Python: functions, classes, and method-call edges', async () => {
    const py = `class Greeter:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return format_msg(self.name)

def format_msg(name):
    return "hi " + name
`;
    const syms = await extractSymbolsAst(py, 'python');
    const names = syms.map((s) => s.name);
    expect(names).toContain('Greeter');
    expect(names).toContain('greet');
    expect(names).toContain('format_msg');

    const edges = await extractCallEdgesAst(py, 'python');
    expect(edges).toContainEqual({ source: 'greet', target: 'format_msg', type: 'calls' });
  });

  it('extracts TypeScript symbols including interfaces', async () => {
    const ts = `export interface User { id: number; }
export class Store {
  find(id: number): User | null { return lookup(id); }
}
function lookup(id: number): User | null { return null; }
`;
    const syms = await extractSymbolsAst(ts, 'typescript');
    const kinds = new Map(syms.map((s) => [s.name, s.kind]));
    expect(kinds.get('User')).toBe('interface');
    expect(kinds.get('Store')).toBe('class');
    expect(kinds.get('lookup')).toBe('function');

    const edges = await extractCallEdgesAst(ts, 'typescript');
    expect(edges).toContainEqual({ source: 'find', target: 'lookup', type: 'calls' });
  });

  it('C++: functions, methods, class/struct/enum/namespace + call edges', async () => {
    const cpp = `namespace app {
class Widget { public: int area() { return compute(); } int compute() { return 1; } };
struct Point { int x; };
enum Color { Red, Green };
int helper(int n) { return n + 1; }
}`;
    const syms = await extractSymbolsAst(cpp, 'cpp');
    const names = syms.map((s) => s.name);
    expect(names).toEqual(expect.arrayContaining(['app', 'Widget', 'Point', 'Color', 'helper', 'area', 'compute']));
    const edges = await extractCallEdgesAst(cpp, 'cpp');
    expect(edges).toContainEqual({ source: 'area', target: 'compute', type: 'calls' });
  });

  it('C#: class/interface/enum/method + invocation edges', async () => {
    const cs = `namespace App {
  interface IShape { int Area(); }
  class Circle : IShape {
    public int Area() { return Compute(); }
    private int Compute() { return 42; }
  }
  enum Color { Red, Green }
}`;
    const syms = await extractSymbolsAst(cs, 'csharp');
    const names = syms.map((s) => s.name);
    expect(names).toEqual(expect.arrayContaining(['IShape', 'Circle', 'Area', 'Compute', 'Color']));
    const edges = await extractCallEdgesAst(cs, 'csharp');
    expect(edges).toContainEqual({ source: 'Area', target: 'Compute', type: 'calls' });
  });

  it('Java: class/interface/enum/method + method-invocation edges', async () => {
    const java = `package app;
interface Shape { int area(); }
class Circle implements Shape {
  public int area() { return compute(); }
  private int compute() { return 42; }
}`;
    const syms = await extractSymbolsAst(java, 'java');
    const names = syms.map((s) => s.name);
    expect(names).toEqual(expect.arrayContaining(['Shape', 'Circle', 'area', 'compute']));
    const edges = await extractCallEdgesAst(java, 'java');
    expect(edges).toContainEqual({ source: 'area', target: 'compute', type: 'calls' });
  });

  it('Go: func/method/type + call edges', async () => {
    const go = `package main
type Circle struct { r int }
func (c Circle) Area() int { return compute(c.r) }
func compute(n int) int { return n * n }
func main() { _ = compute(2) }`;
    const syms = await extractSymbolsAst(go, 'go');
    const names = syms.map((s) => s.name);
    expect(names).toEqual(expect.arrayContaining(['Circle', 'Area', 'compute', 'main']));
    const edges = await extractCallEdgesAst(go, 'go');
    expect(edges).toContainEqual({ source: 'Area', target: 'compute', type: 'calls' });
    expect(edges).toContainEqual({ source: 'main', target: 'compute', type: 'calls' });
  });

  it('HTML: extracts INLINE <script> JS with HTML-relative line numbers, skips external', async () => {
    expect(supportsAst('html')).toBe(true);
    expect(astLanguages()).toContain('html');

    // <script> opens on line 5, so init is on line 6 and render on line 7.
    const html = `<!DOCTYPE html>
<html>
<head><title>t</title></head>
<body>
<script>
function init() { render(); }
function render() { return 1; }
</script>
<script src="vendor.js"></script>
</body>
</html>
`;
    const syms = await extractSymbolsAst(html, 'html');
    const byName = new Map(syms.map((s) => [s.name, s.line]));
    expect(byName.get('init')).toBe(6);   // line-offset maps inline JS back to HTML
    expect(byName.get('render')).toBe(7);
    // the external <script src=...> body is empty -> contributes no phantom symbols
    expect(syms.length).toBe(2);

    const edges = await extractCallEdgesAst(html, 'html');
    expect(edges).toContainEqual({ source: 'init', target: 'render', type: 'calls' });
  });

  it('unknown language degrades to empty (fallback stays with regex)', async () => {
    expect(await extractSymbolsAst('whatever', 'cobol')).toEqual([]);
    expect(await extractCallEdgesAst('whatever', 'cobol')).toEqual([]);
  });

  it('is deterministic: same input -> identical output', async () => {
    const a = await extractSymbolsAst(C_SRC, 'c');
    const b = await extractSymbolsAst(C_SRC, 'c');
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });
});
