// Node smoke test for canvas-precapture.js — fakes Document / Element /
// HTMLCanvasElement / ShadowRoot shapes (no JSDOM) and exercises every
// offline SPEC 03 fixture (1-5). The live fixture (excalidraw) needs a real
// browser and is verified separately via the user's Chrome.
//
// Run: node tools/anatomy-extension/lib/_smoke-canvas.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'canvas-precapture.js'), 'utf8');

class FakeShadowRoot {
  constructor({ mode = 'open', children = [] } = {}) {
    this.mode = mode;
    this.children = children;
  }
  querySelectorAll(sel) {
    const collected = [];
    function walk(n) {
      if (!n) return;
      const list = (n.children || n.childNodes || []);
      for (const c of list) {
        if (sel === 'canvas' && c.localName === 'canvas') collected.push(c);
        else if (sel === '*' && c.nodeType === 1) collected.push(c);
        walk(c);
      }
    }
    walk(this);
    return collected;
  }
}

function makeCanvas({ width = 100, height = 100, throws = false, jpegThrows = null, contextHint = null, pngBytes = 1000 } = {}) {
  const attrs = new Map();
  if (contextHint) attrs.set('data-context-hint', contextHint);
  return {
    nodeType: 1,
    localName: 'canvas',
    tagName: 'CANVAS',
    width,
    height,
    children: [],
    childNodes: [],
    shadowRoot: null,
    getAttribute(name) { return attrs.has(name) ? attrs.get(name) : null; },
    setAttribute(name, value) { attrs.set(name, value); },
    _attrs: attrs,
    toDataURL(type, quality) {
      const t = type || 'image/png';
      if (t === 'image/png' && throws) throw new Error('SecurityError: tainted canvas');
      if (t === 'image/jpeg' && jpegThrows) throw new Error('SecurityError');
      // Return a data URL whose decoded byte length is approximately pngBytes.
      // base64 inflates by 4/3, so b64 chars ≈ pngBytes * 4/3.
      const b64Len = Math.ceil(pngBytes * 4 / 3);
      const b64 = 'A'.repeat(b64Len);
      return 'data:' + (type || 'image/png') + ';base64,' + b64;
    },
    getContext(type) {
      if (type === '2d') return contextHint === 'webgl' || contextHint === 'webgl2' ? null : { _: '2d' };
      if (type === 'webgl') return contextHint === 'webgl' ? { _: 'webgl' } : null;
      if (type === 'webgl2') return contextHint === 'webgl2' ? { _: 'webgl2' } : null;
      return null;
    },
  };
}

function makeElement(tag, { children = [], shadowRoot = null } = {}) {
  return {
    nodeType: 1,
    localName: tag,
    tagName: tag.toUpperCase(),
    children,
    childNodes: children,
    shadowRoot,
    getAttribute() { return null; },
    setAttribute() {},
  };
}

function makeDoc(rootChildren) {
  const root = {
    nodeType: 1,
    localName: 'html',
    children: rootChildren,
    childNodes: rootChildren,
    shadowRoot: null,
    querySelectorAll(sel) {
      const out = [];
      function walk(n) {
        if (!n) return;
        const list = (n.children || n.childNodes || []);
        for (const c of list) {
          if (sel === 'canvas' && c.localName === 'canvas') out.push(c);
          else if (sel === '*' && c.nodeType === 1) out.push(c);
          walk(c);
        }
      }
      walk(this);
      return out;
    },
  };
  return {
    nodeType: 9,
    documentElement: root,
    querySelectorAll(sel) { return root.querySelectorAll(sel); },
  };
}

function loadModule() {
  const win = {};
  const fn = new Function('window', 'performance', 'console', src + '\nreturn window.__anatomyCanvas;');
  return fn(win, { now: () => Date.now() }, console);
}

const results = [];
function assert(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail });
}

// 1. no-canvas → returns count 0, no mutations
{
  const div = makeElement('div', { children: [] });
  const doc = makeDoc([div]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  assert('no-canvas → count 0', r.count === 0 && r.tainted === 0, JSON.stringify(r));
}

// 2. blank-canvas (100x100, captures fine) → data-precapture-src set non-empty
{
  const c = makeCanvas({ width: 100, height: 100 });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  const src = c._attrs.get('data-precapture-src');
  const ok = r.count === 1
    && typeof src === 'string'
    && src.startsWith('data:image/png')
    && c._attrs.get('data-precapture-width') === '100'
    && c._attrs.get('data-precapture-height') === '100';
  assert('blank-canvas → data-precapture-src + dims set', ok, `count=${r.count} src=${src && src.slice(0, 40)} w=${c._attrs.get('data-precapture-width')}`);
}

// 3. drawn-canvas → same path; SPEC differentiates only on pixel content,
//    which we can't validate offline. Verify the data URL is forwarded.
{
  const c = makeCanvas({ width: 50, height: 50, pngBytes: 2048 });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  precaptureCanvases(doc);
  const src = c._attrs.get('data-precapture-src');
  assert('drawn-canvas → data URL forwarded verbatim from toDataURL', src && src.startsWith('data:image/png;base64,A'), src && src.slice(0, 50));
}

// 4. tainted-canvas → status="tainted", no src
{
  const c = makeCanvas({ width: 200, height: 200, throws: true, jpegThrows: true });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  const ok = r.tainted === 1
    && c._attrs.get('data-precapture-status') === 'tainted'
    && !c._attrs.has('data-precapture-src');
  assert('tainted-canvas → status="tainted", no src', ok, JSON.stringify({ r, status: c._attrs.get('data-precapture-status'), hasSrc: c._attrs.has('data-precapture-src') }));
}

// 5. multi-canvas (3 canvases) → returns count 3
{
  const a = makeCanvas({ width: 10, height: 10 });
  const b = makeCanvas({ width: 20, height: 20 });
  const cc = makeCanvas({ width: 30, height: 30 });
  const wrap = makeElement('section', { children: [a, b, cc] });
  const doc = makeDoc([wrap]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  assert('multi-canvas → count 3', r.count === 3, JSON.stringify(r));
}

// 6. taint with PNG but JPEG fallback succeeds → captured (no status)
{
  const c = makeCanvas({ width: 10, height: 10, throws: true, jpegThrows: false });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  const ok = r.count === 1
    && c._attrs.get('data-precapture-src') && c._attrs.get('data-precapture-src').startsWith('data:image/jpeg')
    && !c._attrs.has('data-precapture-status');
  assert('jpeg fallback → captures via image/jpeg', ok, JSON.stringify({ r, src: (c._attrs.get('data-precapture-src') || '').slice(0, 40), status: c._attrs.get('data-precapture-status') }));
}

// 7. 0x0 canvas → skipped, no attributes emitted
{
  const c = makeCanvas({ width: 0, height: 0 });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  const ok = r.skipped === 1
    && r.count === 0
    && !c._attrs.has('data-precapture-src')
    && !c._attrs.has('data-precapture-width')
    && !c._attrs.has('data-precapture-status');
  assert('0x0 canvas → skipped, no attributes', ok, JSON.stringify({ r, attrs: Array.from(c._attrs.keys()) }));
}

// 8. oversize data URL (>10MB) → status="oversize", no src
{
  const c = makeCanvas({ width: 4000, height: 4000, pngBytes: 11 * 1024 * 1024 });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  const ok = r.oversize === 1
    && c._attrs.get('data-precapture-status') === 'oversize'
    && !c._attrs.has('data-precapture-src');
  assert('oversize → status="oversize", no src', ok, JSON.stringify({ r, status: c._attrs.get('data-precapture-status'), hasSrc: c._attrs.has('data-precapture-src') }));
}

// 9. canvas inside open shadow root → captured
{
  const innerCanvas = makeCanvas({ width: 10, height: 10 });
  const sr = new FakeShadowRoot({ children: [innerCanvas] });
  const host = makeElement('my-host', {});
  host.shadowRoot = sr;
  const doc = makeDoc([host]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  const ok = r.count === 1 && innerCanvas._attrs.has('data-precapture-src');
  assert('shadow-root canvas → captured', ok, JSON.stringify({ r, hasSrc: innerCanvas._attrs.has('data-precapture-src') }));
}

// 10. closed shadow root → not traversed (canvas inside is invisible)
{
  const innerCanvas = makeCanvas({ width: 10, height: 10 });
  const sr = new FakeShadowRoot({ mode: 'closed', children: [innerCanvas] });
  const host = makeElement('closed-host', {});
  host.shadowRoot = sr;
  const doc = makeDoc([host]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  const ok = r.count === 0 && !innerCanvas._attrs.has('data-precapture-src');
  assert('closed shadow → canvas inside not captured', ok, JSON.stringify({ r, hasSrc: innerCanvas._attrs.has('data-precapture-src') }));
}

// 11. data-context-hint preferred (no getContext probing of fresh canvas)
{
  const c = makeCanvas({ width: 100, height: 100, contextHint: 'webgl2' });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  precaptureCanvases(doc);
  assert('context hint respected', c._attrs.get('data-precapture-context') === 'webgl2', c._attrs.get('data-precapture-context'));
}

// 12. context detection: 2d after successful capture
{
  const c = makeCanvas({ width: 100, height: 100 });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  precaptureCanvases(doc);
  assert('post-capture 2d detection', c._attrs.get('data-precapture-context') === '2d', c._attrs.get('data-precapture-context'));
}

// 13. tainted canvas without hint → context="unknown" (no probing risk)
{
  const c = makeCanvas({ width: 50, height: 50, throws: true, jpegThrows: true });
  const doc = makeDoc([c]);
  const { precaptureCanvases } = loadModule();
  precaptureCanvases(doc);
  assert('tainted no-hint → context="unknown"', c._attrs.get('data-precapture-context') === 'unknown', c._attrs.get('data-precapture-context'));
}

// 14. circular shadow guard — same shadow seen twice doesn't double-process
{
  const innerCanvas = makeCanvas({ width: 5, height: 5 });
  const sr = new FakeShadowRoot({ children: [innerCanvas] });
  const hostA = makeElement('host-a', {}); hostA.shadowRoot = sr;
  const hostB = makeElement('host-b', {}); hostB.shadowRoot = sr;
  const doc = makeDoc([hostA, hostB]);
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(doc);
  // The canvas appears once in the shared shadow root; the WeakSet guard
  // prevents enumerating it twice.
  assert('shared shadow → counted once', r.count === 1, JSON.stringify(r));
}

// 15. report shape
{
  const { precaptureCanvases } = loadModule();
  const r = precaptureCanvases(makeDoc([]));
  const ok = typeof r === 'object'
    && typeof r.count === 'number'
    && typeof r.tainted === 'number'
    && typeof r.oversize === 'number'
    && typeof r.skipped === 'number'
    && typeof r.elapsedMs === 'number';
  assert('report shape: {count,tainted,oversize,skipped,elapsedMs}', ok, JSON.stringify(r));
}

// ── report ──
let passed = 0;
for (const r of results) {
  const tag = r.ok ? 'PASS' : 'FAIL';
  console.log(`${tag}  ${r.name}${r.ok ? '' : `\n      ${r.detail}`}`);
  if (r.ok) passed++;
}
console.log(`\n${passed}/${results.length} passed`);
process.exit(passed === results.length ? 0 : 1);
