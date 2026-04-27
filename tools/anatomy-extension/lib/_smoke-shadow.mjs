// Node smoke test for shadow-dom-recursion.js — fakes Element / ShadowRoot
// shapes (no JSDOM) and exercises every offline SPEC 02 fixture (1-5). The
// live fixtures (notion-live, linear-live) need a real browser and are
// verified separately via preview tooling.
//
// Run: node tools/anatomy-extension/lib/_smoke-shadow.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'shadow-dom-recursion.js'), 'utf8');

class FakeShadowRoot {
  constructor({ mode = 'open', children = [], adoptedStyleSheets = [], delegatesFocus = false } = {}) {
    this.mode = mode;
    this.childNodes = children;
    this.adoptedStyleSheets = adoptedStyleSheets;
    this.delegatesFocus = delegatesFocus;
  }
}

function loadModule({ adoptedShim } = {}) {
  const win = {};
  if (adoptedShim) win.__anatomyAdoptedStyles = adoptedShim;
  const fn = new Function('window', 'ShadowRoot', src + '\nreturn window.__anatomyShadowDOM;');
  return fn(win, FakeShadowRoot);
}

function el(tag, { attrs = {}, children = [], shadowRoot = null, content = null, textContent = null, outerHTML = null } = {}) {
  const node = {
    nodeType: 1,
    localName: tag,
    tagName: tag.toUpperCase(),
    attributes: Object.entries(attrs).map(([name, value]) => ({ name, value: String(value) })),
    childNodes: children,
    shadowRoot,
    content,
    textContent,
    outerHTML,
    querySelectorAll() {
      const collected = [];
      function walk(n) {
        if (!n || !n.childNodes) return;
        for (const c of n.childNodes) {
          if (c && c.nodeType === 1) {
            collected.push(c);
            walk(c);
          }
        }
      }
      walk(node);
      return collected;
    },
  };
  return node;
}

function text(s) { return { nodeType: 3, nodeValue: s }; }

const results = [];
function assert(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail });
}

// 1. no-shadow.html · plain DOM · output equivalent to outerHTML (fast path)
{
  const expected = '<div class="x">hi</div>';
  const root = el('div', { attrs: { class: 'x' }, children: [text('hi')], outerHTML: expected });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  assert('no-shadow → outerHTML fast path', got === expected, `got=${got}`);
}

// 2. single-shadow.html · open shadow with <p>hi</p>
{
  const p = el('p', { children: [text('hi')] });
  const sr = new FakeShadowRoot({ children: [p] });
  const host = el('my-host', { shadowRoot: sr });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(host);
  const ok = got.includes('<template shadowrootmode="open"><p>hi</p></template>')
    && got.startsWith('<my-host><template')
    && got.endsWith('</my-host>');
  assert('single-shadow → declarative template emitted as first child', ok, got);
}

// 3. nested-shadow.html · shadow inside a shadow
{
  const innerLeaf = el('span', { children: [text('deep')] });
  const innerShadow = new FakeShadowRoot({ children: [innerLeaf] });
  const innerHost = el('inner-host', { shadowRoot: innerShadow });
  const outerShadow = new FakeShadowRoot({ children: [innerHost] });
  const outerHost = el('outer-host', { shadowRoot: outerShadow });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(outerHost);
  const opens = (got.match(/<template shadowrootmode="open">/g) || []).length;
  const ok = opens === 2 && got.includes('<span>deep</span>') && got.includes('<inner-host>');
  assert('nested-shadow → both levels present', ok, got);
}

// 4. delegates-focus.html · open shadow with delegatesFocus
{
  const sr = new FakeShadowRoot({ children: [text('x')], delegatesFocus: true });
  const host = el('focus-host', { shadowRoot: sr });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(host);
  assert('delegates-focus → shadowrootdelegatesfocus attr', got.includes('shadowrootdelegatesfocus'), got);
}

// 5. closed-shadow.html · closed shadow root
{
  const sr = new FakeShadowRoot({ mode: 'closed', children: [el('p', { children: [text('secret')] })] });
  const host = el('closed-host', { shadowRoot: sr, outerHTML: '<closed-host></closed-host>' });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(host);
  // mode=closed in our shim is reachable, but the spec says skip when not "open".
  const ok = !got.includes('secret') && !got.includes('shadowrootmode');
  assert('closed-shadow → contents hidden, no template emitted', ok, got);
}

// 6. shadow-adopted-stylesheets · SPEC 01 integration
{
  const adoptedShim = {
    serializeAdoptedStyles: (root) => ({
      // Identify which root the call was for so the test can prove the shadow
      // root was passed through (not the document).
      styleTags: root && root.__shadowMarker
        ? '<style data-adopted-origin="shadow">.shadow{}</style>'
        : '',
    }),
  };
  const sr = new FakeShadowRoot({ children: [el('p', { children: [text('s')] })] });
  sr.__shadowMarker = true;
  const host = el('styled-host', { shadowRoot: sr });
  const { serializeWithShadow } = loadModule({ adoptedShim });
  const got = serializeWithShadow(host);
  const ok = got.includes('<style data-adopted-origin="shadow">.shadow{}</style>')
    && got.indexOf('<style data-adopted-origin="shadow"')
       < got.indexOf('<p>s</p>');
  assert('shadow adopted sheets prepended inside template', ok, got);
}

// 7. fast-path: subtree without shadows → uses outerHTML even when querySelector reachable
{
  const child = el('span', { children: [text('child')] });
  const root = el('section', { children: [child], outerHTML: '<section><span>child</span></section>' });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  assert('no shadow in tree → outerHTML returned', got === '<section><span>child</span></section>', got);
}

// 8. <template> element handled via .content, not as a shadow host
{
  const frag = { childNodes: [el('em', { children: [text('tpl')] })] };
  const tpl = el('template', { content: frag, attrs: { id: 't1' } });
  const wrapper = el('section', { children: [tpl] });
  // Force slow path by adding a shadow elsewhere
  const dummyShadow = new FakeShadowRoot({ children: [text('s')] });
  const dummyHost = el('dummy', { shadowRoot: dummyShadow });
  const root = el('div', { children: [wrapper, dummyHost] });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  const ok = got.includes('<template id="t1"><em>tpl</em></template>');
  assert('<template> element → uses .content fragment', ok, got);
}

// 9. <script> contents not HTML-escaped
{
  const dummyShadow = new FakeShadowRoot({ children: [text('s')] });
  const dummyHost = el('dummy', { shadowRoot: dummyShadow });
  const script = el('script', { textContent: 'if (a < b) { c = "<x>"; }' });
  const root = el('div', { children: [script, dummyHost] });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  const ok = got.includes('<script>if (a < b) { c = "<x>"; }</script>');
  assert('<script> body preserved verbatim, no escaping', ok, got);
}

// 10. text nodes are HTML-escaped on slow path
{
  const dummyShadow = new FakeShadowRoot({ children: [text('s')] });
  const dummyHost = el('dummy', { shadowRoot: dummyShadow });
  const para = el('p', { children: [text('a < b & c > d')] });
  const root = el('div', { children: [para, dummyHost] });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  const ok = got.includes('<p>a &lt; b &amp; c &gt; d</p>');
  assert('text nodes escaped on slow path', ok, got);
}

// 11. attributes with quotes / entities escape correctly
{
  const dummyShadow = new FakeShadowRoot({ children: [text('s')] });
  const dummyHost = el('dummy', { shadowRoot: dummyShadow });
  const node = el('div', { attrs: { title: 'has "quotes" & <stuff>' } });
  const root = el('section', { children: [node, dummyHost] });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  const ok = got.includes('title="has &quot;quotes&quot; &amp; &lt;stuff>"');
  assert('attribute escape: quotes, ampersands, less-than', ok, got);
}

// 12. void element emitted without closing tag
{
  const dummyShadow = new FakeShadowRoot({ children: [text('s')] });
  const dummyHost = el('dummy', { shadowRoot: dummyShadow });
  const img = el('img', { attrs: { src: 'a.png' } });
  const br = el('br', {});
  const root = el('div', { children: [img, br, dummyHost] });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  const ok = got.includes('<img src="a.png">') && got.includes('<br>') && !got.includes('</img>') && !got.includes('</br>');
  assert('void elements rendered without closing tag', ok, got);
}

// 13. circular shadow guard — same shadow seen twice doesn't recurse
{
  const sr = new FakeShadowRoot({ children: [text('once')] });
  const hostA = el('host-a', { shadowRoot: sr });
  const hostB = el('host-b', { shadowRoot: sr });
  const root = el('div', { children: [hostA, hostB] });
  const { serializeWithShadow } = loadModule();
  const got = serializeWithShadow(root);
  // First host gets the template; second host's duplicate-shadow reference is skipped.
  const onceCount = (got.match(/once/g) || []).length;
  assert('shadow seen twice → emitted once, no infinite loop', onceCount === 1, got);
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
