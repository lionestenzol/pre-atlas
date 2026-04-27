// Node smoke test for text-grid.js — fakes Document / Element / Range /
// TreeWalker shapes (no JSDOM) and exercises buildTextGrid + scoreRegion.
// renderGridOverlay is canvas-dependent and is verified visually via Bruke's
// real Chrome reload (not here).
//
// Run: node tools/anatomy-extension/lib/_smoke-text-grid.mjs

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'text-grid.js'), 'utf8');

const FILTER_ACCEPT = 1;
const FILTER_REJECT = 2;

class FakeRange {
  constructor(node) { this.node = node; }
  selectNodeContents(n) { this.node = n; }
  getClientRects() { return this.node._rects || []; }
}

function makeTextNode(text, rects, parentTag = 'P', visible = true, style = {}) {
  const parent = {
    nodeType: 1,
    tagName: parentTag,
    _visible: visible,
    _style: {
      fontSize: style.fontSize || '16px',
      color: style.color || 'rgb(0, 0, 0)',
      backgroundColor: style.backgroundColor || 'rgb(255, 255, 255)',
    },
    parentElement: null,
  };
  return {
    nodeType: 3,
    nodeValue: text,
    parentElement: parent,
    _rects: rects,
  };
}

function makeWindow({ scrollX = 0, scrollY = 0, scrollW = 1000, scrollH = 1000 } = {}) {
  return {
    window: { scrollX, scrollY },
    documentElement: { scrollWidth: scrollW, scrollHeight: scrollH, clientWidth: scrollW, clientHeight: scrollH },
    body: { scrollWidth: scrollW, scrollHeight: scrollH },
  };
}

function evalModule(textNodes, env) {
  const w = env.window;
  const NodeFilter = { SHOW_TEXT: 4, FILTER_ACCEPT, FILTER_REJECT };
  const fakeWalker = (root, what, filter) => {
    const queue = [...textNodes];
    return {
      nextNode() {
        while (queue.length) {
          const n = queue.shift();
          const verdict = filter && filter.acceptNode ? filter.acceptNode(n) : FILTER_ACCEPT;
          if (verdict === FILTER_ACCEPT) return n;
        }
        return null;
      },
    };
  };
  const document = {
    documentElement: env.documentElement,
    body: env.body,
    createTreeWalker: fakeWalker,
    createRange: () => new FakeRange(null),
    getElementById: () => null,
    createElement: (tag) => ({ tagName: tag.toUpperCase(), style: { cssText: '' }, appendChild() {} }),
  };
  const getComputedStyle = (el) => ({
    display: el && el._visible === false ? 'none' : 'block',
    visibility: 'visible',
    opacity: '1',
    fontSize: (el && el._style && el._style.fontSize) || '16px',
    color: (el && el._style && el._style.color) || 'rgb(0, 0, 0)',
    backgroundColor: (el && el._style && el._style.backgroundColor) || 'rgb(255, 255, 255)',
  });
  const ShadowRoot = function () {};
  const sandbox = {
    window: { scrollX: w.scrollX, scrollY: w.scrollY, getComputedStyle, ShadowRoot, __anatomyTextGrid: undefined },
    document,
    NodeFilter,
    ShadowRoot,
    HTMLElement: function () {},
  };
  // text-grid.js reads `window` and `document` as free globals. Hoist into
  // the function scope so the IIFE sees them.
  const wrapped = `with (env) { ${src} } return env.window.__anatomyTextGrid;`;
  // eslint-disable-next-line no-new-func
  const fn = new Function('env', wrapped);
  return fn({ ...sandbox, getComputedStyle });
}

let pass = 0, fail = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`PASS  ${name}`);
    pass++;
  } catch (e) {
    console.log(`FAIL  ${name}`);
    console.log(`      ${e.message}`);
    fail++;
  }
}
function eq(a, b, msg) {
  if (a !== b) throw new Error(`${msg || ''} expected ${b}, got ${a}`);
}
function gt(a, b, msg) {
  if (!(a > b)) throw new Error(`${msg || ''} expected >${b}, got ${a}`);
}
function ge(a, b, msg) {
  if (!(a >= b)) throw new Error(`${msg || ''} expected >=${b}, got ${a}`);
}

// ── Fixtures ──────────────────────────────────────────────────────────

test('empty page → grid all zeros', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const api = evalModule([], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  eq(grid.cols, 10, 'cols');
  eq(grid.rows, 10, 'rows');
  eq(grid.max, 0, 'max');
  eq(grid.textNodes, 0, 'textNodes');
  let sum = 0;
  for (let i = 0; i < grid.cells.length; i++) sum += grid.cells[i];
  eq(sum, 0, 'cell sum');
});

test('single text node marks cells overlapping its rect', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const node = makeTextNode('Hello world', [
    { left: 24, top: 24, right: 72, bottom: 48, width: 48, height: 24 },
  ]);
  const api = evalModule([node], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  // Rect spans cols 1..2, row 1 only.
  eq(grid.cells[1 * grid.cols + 1] > 0, true, 'cell (1,1) marked');
  eq(grid.cells[1 * grid.cols + 2] > 0, true, 'cell (1,2) marked');
  // Cells outside the rect must stay 0.
  eq(grid.cells[0], 0, 'cell (0,0) untouched');
  eq(grid.cells[2 * grid.cols + 1], 0, 'cell (2,1) untouched');
  eq(grid.textNodes, 1);
});

test('two text nodes far apart → only their cells marked, gap zero', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const a = makeTextNode('aa', [{ left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 }]);
  const b = makeTextNode('bb', [{ left: 192, top: 192, right: 216, bottom: 216, width: 24, height: 24 }]);
  const api = evalModule([a, b], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  gt(grid.cells[0], 0, 'A cell marked');
  gt(grid.cells[8 * grid.cols + 8], 0, 'B cell marked');
  // Middle of grid stays 0.
  eq(grid.cells[4 * grid.cols + 4], 0, 'gap cell zero');
});

test('script/style/noscript text excluded', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const ok = makeTextNode('visible', [{ left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 }]);
  const skipScript = makeTextNode('hidden code', [{ left: 0, top: 24, right: 24, bottom: 48, width: 24, height: 24 }], 'SCRIPT');
  const skipStyle  = makeTextNode('css', [{ left: 0, top: 48, right: 24, bottom: 72, width: 24, height: 24 }], 'STYLE');
  const skipNos    = makeTextNode('fallback', [{ left: 0, top: 72, right: 24, bottom: 96, width: 24, height: 24 }], 'NOSCRIPT');
  const api = evalModule([ok, skipScript, skipStyle, skipNos], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  eq(grid.textNodes, 1, 'only the visible node counted');
  gt(grid.cells[0], 0, 'visible cell marked');
  eq(grid.cells[1 * grid.cols + 0], 0, 'script cell skipped');
  eq(grid.cells[2 * grid.cols + 0], 0, 'style cell skipped');
  eq(grid.cells[3 * grid.cols + 0], 0, 'noscript cell skipped');
});

test('hidden parent (display:none) excluded', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const ok = makeTextNode('shown', [{ left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 }]);
  const hidden = makeTextNode('not shown', [{ left: 24, top: 0, right: 48, bottom: 24, width: 24, height: 24 }], 'P', false);
  const api = evalModule([ok, hidden], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  gt(grid.cells[0], 0, 'visible cell marked');
  eq(grid.cells[1], 0, 'hidden cell skipped');
});

test('text node with no rects (collapsed) skipped without crashing', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const empty = makeTextNode('collapsed', []);
  const api = evalModule([empty], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  eq(grid.max, 0, 'max stays zero');
});

test('text length distributes across multi-line rects', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  // Two-line wrapped text: same node, two line rects.
  const node = makeTextNode('first line text and second line text', [
    { left: 0, top: 0, right: 96, bottom: 24, width: 96, height: 24 },
    { left: 0, top: 24, right: 72, bottom: 48, width: 72, height: 24 },
  ]);
  const api = evalModule([node], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  // Both row 0 and row 1 should have density.
  let row0 = 0, row1 = 0;
  for (let c = 0; c < grid.cols; c++) {
    row0 += grid.cells[0 * grid.cols + c];
    row1 += grid.cells[1 * grid.cols + c];
  }
  gt(row0, 0, 'row 0 marked');
  gt(row1, 0, 'row 1 marked');
});

test('scoreRegion: returns 0 for empty grid', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const api = evalModule([], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  eq(api.scoreRegion(grid, { x: 0, y: 0, w: 100, h: 100 }), 0);
});

test('scoreRegion: returns 0 for zero-area rect', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const node = makeTextNode('hello', [{ left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 }]);
  const api = evalModule([node], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  eq(api.scoreRegion(grid, { x: 0, y: 0, w: 0, h: 0 }), 0);
});

test('scoreRegion: high-text region scores higher than empty region', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const dense = makeTextNode('lots of words here filling cells', [
    { left: 0, top: 0, right: 96, bottom: 24, width: 96, height: 24 },
  ]);
  const api = evalModule([dense], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  const hot = api.scoreRegion(grid, { x: 0, y: 0, w: 96, h: 24 });
  const cold = api.scoreRegion(grid, { x: 0, y: 96, w: 96, h: 24 });
  gt(hot, cold, 'hot region beats cold');
  ge(cold, 0, 'cold is non-negative');
});

test('scoreRegion: clips out-of-bounds rect to grid', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const node = makeTextNode('hi', [{ left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 }]);
  const api = evalModule([node], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  // Region extends past page bottom-right; should still return a valid number.
  const score = api.scoreRegion(grid, { x: 0, y: 0, w: 1000, h: 1000 });
  ge(score, 0, 'clipped score is non-negative');
});

test('scoreRegion: rect entirely outside grid returns 0', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const node = makeTextNode('hi', [{ left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 }]);
  const api = evalModule([node], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  // Rect way past page bottom-right.
  const score = api.scoreRegion(grid, { x: 5000, y: 5000, w: 100, h: 100 });
  eq(score, 0, 'far-away rect is zero');
});

test('grid dimensions scale with cellPx', () => {
  const env = makeWindow({ scrollW: 480, scrollH: 240 });
  const api = evalModule([], env);
  const big = api.buildTextGrid({ cellPx: 48 });
  eq(big.cols, 10);
  eq(big.rows, 5);
  const small = api.buildTextGrid({ cellPx: 12 });
  eq(small.cols, 40);
  eq(small.rows, 20);
});

test('cellPx defaults to 24 when not provided', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  const api = evalModule([], env);
  const grid = api.buildTextGrid({});
  eq(grid.cellPx, 24);
});

// ── Prominence weighting (Phase A · char count → fontSize²×contrast) ──

test('big headline outranks small body text (per-cell prominence)', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  // Same physical area: 1 cell each. Headline is 28px, body is 11px.
  const headline = makeTextNode('BIG', [
    { left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 },
  ], 'H1', true, { fontSize: '28px', color: 'rgb(0, 0, 0)' });
  const body = makeTextNode('lots of small body chars here', [
    { left: 0, top: 24, right: 24, bottom: 48, width: 24, height: 24 },
  ], 'P', true, { fontSize: '11px', color: 'rgb(120, 120, 120)' });
  const api = evalModule([headline, body], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  const hScore = api.scoreRegion(grid, { x: 0, y: 0, w: 24, h: 24 });
  const bScore = api.scoreRegion(grid, { x: 0, y: 24, w: 24, h: 24 });
  gt(hScore, bScore * 4, 'headline beats body by 4x+');
});

test('high-contrast text outranks low-contrast at same size', () => {
  const env = makeWindow({ scrollW: 240, scrollH: 240 });
  // Same font size. One is black-on-white (max contrast), one is light gray
  // on white (low contrast · decoration).
  const high = makeTextNode('hi', [
    { left: 0, top: 0, right: 24, bottom: 24, width: 24, height: 24 },
  ], 'P', true, { fontSize: '16px', color: 'rgb(0, 0, 0)' });
  const low  = makeTextNode('hi', [
    { left: 0, top: 24, right: 24, bottom: 48, width: 24, height: 24 },
  ], 'P', true, { fontSize: '16px', color: 'rgb(220, 220, 220)' });
  const api = evalModule([high, low], env);
  const grid = api.buildTextGrid({ cellPx: 24 });
  const hi = api.scoreRegion(grid, { x: 0, y: 0, w: 24, h: 24 });
  const lo = api.scoreRegion(grid, { x: 0, y: 24, w: 24, h: 24 });
  gt(hi, lo * 3, 'high contrast beats low contrast');
});

console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail === 0 ? 0 : 1);
