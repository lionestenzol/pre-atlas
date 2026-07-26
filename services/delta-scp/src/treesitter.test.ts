import { describe, it, expect } from 'vitest';
import { extractSymbols } from './compressor.js';
import {
  extractSymbolsAst,
  extractCallEdgesAst,
  extractQualifiedCallEdgesAst,
  extractPropertyAssignmentsAst,
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

  it('JS/TS: member-style calls (document.write, child_process.exec) are now visible — the call query was blind to anything but a bare identifier', async () => {
    const js = `function render(data) {
  document.write(data);
  child_process.exec(data);
  helper();
}
function helper() {}`;
    const edges = await extractCallEdgesAst(js, 'javascript');
    const targets = edges.map((e) => e.target);
    expect(targets).toContain('write');
    expect(targets).toContain('exec');
    // member calls are tagged `qualified: true` — distinguishes child_process.exec
    // from a bare exec(x), so a receiver-check can be required for collision-prone
    // names (see modernize.ts RISKY_QUALIFIED_TARGETS / EXEC_FAMILY_TARGETS).
    expect(edges).toContainEqual({ source: 'render', target: 'write', type: 'calls', qualified: true });
    expect(edges).toContainEqual({ source: 'render', target: 'exec', type: 'calls', qualified: true });
    // bare-identifier calls still work (no regression) and are NOT tagged qualified
    expect(edges).toContainEqual({ source: 'render', target: 'helper', type: 'calls' });
  });

  it('JS/TS: qualified-call extraction distinguishes document.write from an unrelated res.write (bare "write" is too generic to denylist alone)', async () => {
    const js = `function render(data) {
  document.write(data);
  res.write(data);
}`;
    const qualified = await extractQualifiedCallEdgesAst(js, 'javascript');
    const targets = qualified.map((e) => e.target);
    expect(targets).toContain('document.write');
    expect(targets).toContain('res.write'); // extractor is unfiltered; modernize.ts's
    // RISKY_QUALIFIED_TARGETS denylist is what keeps only document.write flagged as risky.
    expect(qualified.every((e) => e.source === 'render')).toBe(true);
  });

  it('JS/TS: qualified-call capture handles a CHAINED receiver (this.db.exec), not just a bare-identifier object — the exact delta-kernel false-positive shape', async () => {
    const js = `class Store {
  constructor(db) {
    this.db = db;
    this.db.exec('CREATE TABLE t (id)');
  }
}`;
    const qualified = await extractQualifiedCallEdgesAst(js, 'javascript');
    expect(qualified.map((e) => e.target)).toContain('this.db.exec');
  });

  it('Python: qualified-call extraction captures the full attribute chain (os.system, pickle.loads) — previously unsupported, python had no qualifiedCallQuery at all', async () => {
    const py = `import os, pickle
def run(cmd, blob):
    os.system(cmd)
    pickle.loads(blob)
`;
    const qualified = await extractQualifiedCallEdgesAst(py, 'python');
    const targets = qualified.map((e) => e.target);
    expect(targets).toContain('os.system');
    expect(targets).toContain('pickle.loads');
    expect(qualified.every((e) => e.source === 'run')).toBe(true);
  });

  it('JS/TS: property-assignment sinks (el.innerHTML = x) are now visible — a call-only scan cannot see an assignment', async () => {
    const js = `function updateZoneLogsUI(container, log) {
  container.innerHTML = '';
  const item = document.createElement('div');
  item.innerHTML = log.location;
}`;
    const assigns = await extractPropertyAssignmentsAst(js, 'javascript');
    const props = assigns.map((a) => a.property);
    expect(props).toContain('innerHTML');
    expect(assigns.every((a) => a.source === 'updateZoneLogsUI')).toBe(true);
  });

  it('assignment attribution walks PAST an anonymous forEach/arrow callback to the nearest NAMED function — not "(module scope)"', async () => {
    // The exact real-world shape from URBANNOMAD's historical S1 finding: the
    // sink sits inside an anonymous forEach callback nested in a named function.
    const js = `function updateZoneLogsUI(container, logs) {
    logs.forEach((log) => {
        const item = document.createElement('div');
        item.innerHTML = log.location;
        container.appendChild(item);
    });
}`;
    const assigns = await extractPropertyAssignmentsAst(js, 'javascript');
    const hit = assigns.find((a) => a.property === 'innerHTML');
    expect(hit?.source).toBe('updateZoneLogsUI');
  });

  it('property-assignment scan stays precise: ordinary properties are captured but NOT the DOM-sink denylist test (that filtering lives in modernize.ts)', async () => {
    // extractPropertyAssignmentsAst is a raw extractor — it returns every property
    // assignment, unfiltered. Precision (only innerHTML/outerHTML count as risky)
    // is enforced by DOM_SINK_PROPS in modernize.ts's collectRiskySurfaces, not
    // here. This test just proves ordinary assignments (e.g. .href, .value) are
    // captured too, so the denylist filter downstream has real data to filter.
    const js = `function nav(a) { a.href = '/x'; a.value = 1; }`;
    const assigns = await extractPropertyAssignmentsAst(js, 'javascript');
    const props = assigns.map((a) => a.property);
    expect(props).toEqual(expect.arrayContaining(['href', 'value']));
  });

  it('TypeScript: member-call and assignment sinks both work (not just JS)', async () => {
    const ts = `function render(data: string) {
  document.write(data);
  const el: HTMLElement = document.body;
  el.innerHTML = data;
}`;
    const edges = await extractCallEdgesAst(ts, 'typescript');
    expect(edges.map((e) => e.target)).toContain('write');
    const qualified = await extractQualifiedCallEdgesAst(ts, 'typescript');
    expect(qualified.map((e) => e.target)).toContain('document.write');
    const assigns = await extractPropertyAssignmentsAst(ts, 'typescript');
    expect(assigns.map((a) => a.property)).toContain('innerHTML');
  });

  it('HTML: inline <script> member-calls and assignment sinks both surface through the html delegation path', async () => {
    const html = `<html><body>
<script>
function render(data) {
  document.write(data);
  el.innerHTML = data;
}
</script>
</body></html>`;
    const edges = await extractCallEdgesAst(html, 'html');
    expect(edges.map((e) => e.target)).toContain('write');
    const qualified = await extractQualifiedCallEdgesAst(html, 'html');
    expect(qualified.map((e) => e.target)).toContain('document.write');
    const assigns = await extractPropertyAssignmentsAst(html, 'html');
    expect(assigns.map((a) => a.property)).toContain('innerHTML');
  });

  it('languages without assignQuery/qualifiedCallQuery (C) return empty rather than throwing', async () => {
    expect(await extractPropertyAssignmentsAst('int x = 1;', 'c')).toEqual([]);
    expect(await extractQualifiedCallEdgesAst('int x = 1;', 'c')).toEqual([]);
  });

  it('unknown language degrades to empty (fallback stays with regex)', async () => {
    expect(await extractSymbolsAst('whatever', 'cobol')).toEqual([]);
    expect(await extractCallEdgesAst('whatever', 'cobol')).toEqual([]);
    expect(await extractQualifiedCallEdgesAst('whatever', 'cobol')).toEqual([]);
    expect(await extractPropertyAssignmentsAst('whatever', 'cobol')).toEqual([]);
  });

  it('is deterministic: same input -> identical output', async () => {
    const a = await extractSymbolsAst(C_SRC, 'c');
    const b = await extractSymbolsAst(C_SRC, 'c');
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });
});
