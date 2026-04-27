// Node smoke test for adopted-stylesheets.js — no JSDOM, shim the bits we use.
// Exercises every SPEC 01 failure mode + measurable test case we can fake
// without a live page (fixture 6, linear-live, needs the real browser).
//
// Run: node tools/anatomy-extension/lib/_smoke.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'adopted-stylesheets.js'), 'utf8');

function loadWith(shadowRootCtor) {
  const win = {};
  const sandbox = { window: win, ShadowRoot: shadowRootCtor };
  const fn = new Function('window', 'ShadowRoot', src + '\nreturn window.__anatomyAdoptedStyles;');
  return fn(win, shadowRootCtor);
}

// Fake CSSStyleSheet: returns whatever rule list we give it.
function fakeSheet(rules, { disabled = false, throwOnAccess = false } = {}) {
  return {
    disabled,
    get cssRules() {
      if (throwOnAccess) throw new Error('SecurityError: cross-origin');
      return rules;
    },
  };
}
function rule(cssText) { return { cssText }; }

class FakeShadowRoot {}

const mod = loadWith(FakeShadowRoot);
const { serializeAdoptedStyles } = mod;

const results = [];
function assert(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail });
}

// 1. empty — no adopted sheets
{
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [] });
  assert('empty: no sheets → ""', r.styleTags === '', JSON.stringify(r));
}

// 2. unsupported — adoptedStyleSheets undefined
{
  const r = serializeAdoptedStyles({});
  assert('unsupported: no property → ""', r.styleTags === '', JSON.stringify(r));
}

// 3. null root
{
  const r = serializeAdoptedStyles(null);
  assert('null root → ""', r.styleTags === '', JSON.stringify(r));
}

// 4. single rule, document origin
{
  const s = fakeSheet([rule('.red { color: red }')]);
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [s] });
  const ok = r.styleTags.includes('.red { color: red }')
    && r.styleTags.includes('data-adopted-origin="root"')
    && !r.styleTags.includes('data-adopted-disabled');
  assert('single rule → one tag with origin=root', ok, r.styleTags);
}

// 5. media-query rule preserved verbatim
{
  const s = fakeSheet([rule('@media (max-width: 500px) { .x { color: blue } }')]);
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [s] });
  assert(
    'media: preserves @media wrapper',
    r.styleTags.includes('@media (max-width: 500px) { .x { color: blue } }'),
    r.styleTags,
  );
}

// 6. shadow root origin
{
  const fakeShadow = Object.assign(new FakeShadowRoot(), {
    adoptedStyleSheets: [fakeSheet([rule('.y { color: green }')])],
  });
  const r = serializeAdoptedStyles(fakeShadow);
  assert(
    'shadow: origin=shadow',
    r.styleTags.includes('data-adopted-origin="shadow"') && r.styleTags.includes('.y { color: green }'),
    r.styleTags,
  );
}

// 7. disabled sheet still emitted but marked disabled
{
  const s = fakeSheet([rule('.z { color: gray }')], { disabled: true });
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [s] });
  assert(
    'disabled: data-adopted-disabled="1"',
    r.styleTags.includes('data-adopted-disabled="1"') && r.styleTags.includes('.z { color: gray }'),
    r.styleTags,
  );
}

// 8. sheet with no rules → skipped entirely
{
  const s = fakeSheet([]);
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [s] });
  assert('zero rules → no empty tag', r.styleTags === '', r.styleTags);
}

// 9. rule with empty cssText → skipped
{
  const s = fakeSheet([rule('')]);
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [s] });
  assert('empty cssText → no empty tag', r.styleTags === '', r.styleTags);
}

// 10. cssRules throws → that sheet skipped, next one still emits
{
  const bad = fakeSheet([], { throwOnAccess: true });
  const good = fakeSheet([rule('.ok { color: black }')]);
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [bad, good] });
  const ok = r.styleTags.includes('.ok { color: black }')
    && !r.styleTags.includes('cross-origin');
  assert('access throws → skip sheet, continue', ok, r.styleTags);
}

// 11. </style> literal in rule text → split across tags, no raw terminator
{
  const s = fakeSheet([rule('.a { content: "</style>" } .b { color: red }')]);
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [s] });
  // Count raw `</style>` occurrences — should equal number of opening <style
  const openCount = (r.styleTags.match(/<style /gi) || []).length;
  const closeCount = (r.styleTags.match(/<\/style>/gi) || []).length;
  assert(
    '</style> literal → split across tags, balanced',
    openCount === closeCount && openCount >= 2,
    `open=${openCount} close=${closeCount} html=${r.styleTags}`,
  );
}

// 12. multiple rules in one sheet → joined in order
{
  const s = fakeSheet([rule('.first { x: 1 }'), rule('.second { x: 2 }'), rule('.third { x: 3 }')]);
  const r = serializeAdoptedStyles({ adoptedStyleSheets: [s] });
  const pos1 = r.styleTags.indexOf('.first');
  const pos2 = r.styleTags.indexOf('.second');
  const pos3 = r.styleTags.indexOf('.third');
  assert('rule order preserved', pos1 >= 0 && pos1 < pos2 && pos2 < pos3, r.styleTags);
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
