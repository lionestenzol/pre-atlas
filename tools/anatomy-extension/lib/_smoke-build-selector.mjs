// Node smoke test for content.js · buildSelector(el) — extracts the function
// source from content.js and runs it against a fake DOM. No JSDOM.
//
// Locks the contract that downstream consumers (canvas-engine leafTag,
// trainer-vs-truth.mjs, mine_cascade.py) rely on:
//
//   · Elements with a valid id MUST emit `tag#id` (e.g. `a#docs`,
//     `input#search`, `header#masthead`) — not bare `#id` — so the leaf tag
//     stays recoverable from the selector path.
//
//   · Elements without a valid id MUST emit a `:nth-of-type` chain joined by
//     ' > ' so the selector resolves uniquely under querySelector.
//
// Run: node tools/anatomy-extension/lib/_smoke-build-selector.mjs

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', 'content.js'), 'utf8');

// Pull just the buildSelector function out of content.js so the smoke test
// stays in lockstep with the production source.
const match = src.match(/function buildSelector\(el\) \{[\s\S]*?\n  \}/);
if (!match) {
  console.error('FAIL · could not locate buildSelector in content.js');
  process.exit(1);
}
const buildSelectorSrc = match[0];

// Minimal Element-like shape that satisfies the function:
//   · instanceof Element check (line: `if (!(el instanceof Element))`)
//   · .id, .tagName, .parentElement, .parentElement.children
//   · iterating up to document.body
class FakeElement {
  constructor({ tag, id = '', parent = null } = {}) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.parentElement = parent;
    this.children = [];
    if (parent) parent.children.push(this);
  }
}

// Build a minimal tree: body > root > ... > leaf
function makeTree(tagPath, options = {}) {
  // tagPath: array of tag names from root to leaf, e.g. ['div', 'nav', 'a']
  // options: { ids: { idx: 'idValue' }, leafId, siblingTagsByIdx }
  const body = new FakeElement({ tag: 'body' });
  let parent = body;
  const chain = [];
  for (let i = 0; i < tagPath.length; i++) {
    const el = new FakeElement({
      tag: tagPath[i],
      id: (options.ids && options.ids[i]) || '',
      parent,
    });
    chain.push(el);
    parent = el;
  }
  return { body, leaf: chain[chain.length - 1], chain };
}

function evalBuildSelector(body) {
  const fakeDocument = { body };
  const wrapped = `${buildSelectorSrc}\n;return buildSelector;`;
  // eslint-disable-next-line no-new-func
  const fn = new Function('Element', 'document', wrapped);
  return fn(FakeElement, fakeDocument);
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
  if (a !== b) throw new Error(`${msg || ''} expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`);
}

// ── id fast-path · the producer-side fix from this session ────────────────

test('<a id="docs"> emits "a#docs", not "#docs"', () => {
  const { body, leaf } = makeTree(['div', 'nav', 'a'], { ids: { 2: 'docs' } });
  const sel = evalBuildSelector(body)(leaf);
  eq(sel, 'a#docs', 'leaf tag must be recoverable');
});

test('<input id="search"> emits "input#search"', () => {
  const { body, leaf } = makeTree(['form', 'input'], { ids: { 1: 'search' } });
  const sel = evalBuildSelector(body)(leaf);
  eq(sel, 'input#search');
});

test('<button id="save"> emits "button#save"', () => {
  const { body, leaf } = makeTree(['div', 'button'], { ids: { 1: 'save' } });
  const sel = evalBuildSelector(body)(leaf);
  eq(sel, 'button#save');
});

test('<header id="masthead"> emits "header#masthead"', () => {
  const { body, leaf } = makeTree(['header'], { ids: { 0: 'masthead' } });
  const sel = evalBuildSelector(body)(leaf);
  eq(sel, 'header#masthead');
});

test('<select id="country"> emits "select#country" (TAG_OVERRIDES routing)', () => {
  const { body, leaf } = makeTree(['form', 'select'], { ids: { 1: 'country' } });
  const sel = evalBuildSelector(body)(leaf);
  eq(sel, 'select#country');
});

test('<ul id="nav-links"> emits "ul#nav-links" (hyphen in id allowed)', () => {
  const { body, leaf } = makeTree(['nav', 'ul'], { ids: { 1: 'nav-links' } });
  const sel = evalBuildSelector(body)(leaf);
  eq(sel, 'ul#nav-links');
});

// ── id rejection · invalid characters force fallback to chain ─────────────

test('id with spaces falls through to nth-of-type chain', () => {
  const { body, leaf } = makeTree(['div', 'a'], { ids: { 1: 'invalid space' } });
  const sel = evalBuildSelector(body)(leaf);
  // chain doesn't start with `#`, must contain combinator `>`
  eq(sel.startsWith('#'), false, 'must not return bare #invalid space');
  eq(sel.includes(' > '), true, 'must use combinator chain');
  eq(sel.endsWith('a'), true, 'must end at <a>');
});

test('id starting with digit falls through to chain', () => {
  const { body, leaf } = makeTree(['div', 'a'], { ids: { 1: '123abc' } });
  const sel = evalBuildSelector(body)(leaf);
  eq(sel.startsWith('#'), false);
  eq(sel.includes(' > '), true);
});

// ── no-id chain path (regression: still works after the id fast-path edit) ─

test('element without id emits :nth-of-type chain', () => {
  const { body, leaf } = makeTree(['div', 'nav', 'a']);
  const sel = evalBuildSelector(body)(leaf);
  eq(sel, 'div > nav > a');
});

test('chain caps at 9 segments (parts.length > 8 break in production)', () => {
  // Build 12-deep chain → loop unshifts each part then breaks when length > 8
  const tags = Array(12).fill('div').concat(['a']);
  const { body, leaf } = makeTree(tags);
  const sel = evalBuildSelector(body)(leaf);
  const segments = sel.split(' > ');
  if (segments.length > 9) {
    throw new Error(`expected ≤9 segments, got ${segments.length}`);
  }
});

// ── invalid-input handling ────────────────────────────────────────────────

test('non-element input returns null', () => {
  const { body } = makeTree(['div']);
  const buildSelector = evalBuildSelector(body);
  eq(buildSelector(null), null);
  eq(buildSelector(undefined), null);
  eq(buildSelector('not an element'), null);
});

// ── Cross-check: the format must be parseable by canvas-engine leafTag ────
// Mirror the consumer-side splitter so any drift is caught here too.

function consumerLeafTag(selector) {
  if (!selector) return null;
  const segs = selector.trim().split(/\s*[>+~]\s*|\s+/);
  const last = segs[segs.length - 1] || '';
  const m = /^([a-zA-Z][a-zA-Z0-9-]*)/.exec(last);
  return m ? m[1].toLowerCase() : null;
}

test('every id-style emission is leaf-tag-decodable downstream', () => {
  for (const [tags, id, expectedTag] of [
    [['div', 'nav', 'a'],     'docs',       'a'],
    [['form', 'input'],       'search',     'input'],
    [['div', 'button'],       'save',       'button'],
    [['header'],              'masthead',   'header'],
    [['form', 'select'],      'country',    'select'],
    [['nav', 'ul'],           'nav-links',  'ul'],
  ]) {
    const ids = { [tags.length - 1]: id };
    const { body, leaf } = makeTree(tags, { ids });
    const sel = evalBuildSelector(body)(leaf);
    const decoded = consumerLeafTag(sel);
    eq(decoded, expectedTag, `selector="${sel}" should leaf-decode to <${expectedTag}>`);
  }
});

test('every chain emission is leaf-tag-decodable downstream', () => {
  for (const [tags, expectedTag] of [
    [['div', 'a'],            'a'],
    [['form', 'textarea'],    'textarea'],
    [['nav', 'ul'],           'ul'],
    [['div', 'header'],       'header'],
  ]) {
    const { body, leaf } = makeTree(tags);
    const sel = evalBuildSelector(body)(leaf);
    const decoded = consumerLeafTag(sel);
    eq(decoded, expectedTag, `selector="${sel}" should leaf-decode to <${expectedTag}>`);
  }
});

console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail === 0 ? 0 : 1);
