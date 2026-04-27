// Node smoke test for runtime-inline-styles.js — shims <style> elements,
// verifies we emit rehydrated tags only when CSSOM outpaces textContent.
//
// Run: node tools/anatomy-extension/lib/_smoke-inline.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'runtime-inline-styles.js'), 'utf8');

function loadWith(styleEls) {
  const fakeDoc = { querySelectorAll: (sel) => (sel === 'style' ? styleEls : []) };
  const win = {};
  const fn = new Function('window', 'document', src + '\nreturn window.__anatomyInlineStyles;');
  return fn(win, fakeDoc);
}

function fakeEl({ textContent = '', attrs = {}, rules = [], throwOnAccess = false } = {}) {
  const attributes = Object.entries(attrs).map(([name, value]) => ({ name, value }));
  return {
    textContent,
    attributes,
    get sheet() {
      return {
        get cssRules() {
          if (throwOnAccess) throw new Error('cross-origin');
          return rules;
        },
      };
    },
  };
}
function rule(cssText) { return { cssText }; }

const results = [];
function assert(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail });
}

// 1. No style tags at all
{
  const { serializeRuntimeInlineStyles } = loadWith([]);
  const r = serializeRuntimeInlineStyles();
  assert('no tags → empty', r.styleTags === '' && r.rehydratedCount === 0);
}

// 2. Inline style with matching textContent (already in HTML) → skip
{
  const css = '.a { color: red }';
  const el = fakeEl({ textContent: css, rules: [rule(css)] });
  const { serializeRuntimeInlineStyles } = loadWith([el]);
  const r = serializeRuntimeInlineStyles();
  assert('already-serialized → skip', r.styleTags === '' && r.rehydratedCount === 0);
}

// 3. styled-components case: empty textContent + rules present → rehydrate
{
  const el = fakeEl({
    textContent: '',
    attrs: { 'data-styled': 'active', 'data-styled-version': '6.1.24' },
    rules: [rule('.hero { font-size: 4rem }'), rule('.quote { color: #123 }')],
  });
  const { serializeRuntimeInlineStyles } = loadWith([el]);
  const r = serializeRuntimeInlineStyles();
  const ok = r.rehydratedCount === 1
    && r.styleTags.includes('.hero { font-size: 4rem }')
    && r.styleTags.includes('.quote { color: #123 }')
    && r.styleTags.includes('data-runtime-rehydrated="1"')
    && r.styleTags.includes('data-styled="active"')
    && r.styleTags.includes('data-styled-version="6.1.24"');
  assert('styled-components empty tag → rehydrate with attrs preserved', ok, r.styleTags);
}

// 4. cssRules access throws (security) → skip cleanly
{
  const el = fakeEl({ textContent: '', throwOnAccess: true, rules: [] });
  const { serializeRuntimeInlineStyles } = loadWith([el]);
  const r = serializeRuntimeInlineStyles();
  assert('access throws → skip, no crash', r.styleTags === '' && r.rehydratedCount === 0);
}

// 5. Mixed: one styled-components, one authored → rehydrate only first
{
  const authored = fakeEl({ textContent: '.x { color: red }', rules: [rule('.x { color: red }')] });
  const dynamic = fakeEl({ textContent: '', rules: [rule('.y { color: blue }')] });
  const { serializeRuntimeInlineStyles } = loadWith([authored, dynamic]);
  const r = serializeRuntimeInlineStyles();
  const ok = r.rehydratedCount === 1
    && r.styleTags.includes('.y { color: blue }')
    && !r.styleTags.includes('.x { color: red }');
  assert('mixed: only rehydrate dynamic', ok, r.styleTags);
}

// 6. </style> in string → split across tags, balanced
{
  const el = fakeEl({
    textContent: '',
    rules: [rule('.a { content: "</style>" } .b { color: red }')],
  });
  const { serializeRuntimeInlineStyles } = loadWith([el]);
  const r = serializeRuntimeInlineStyles();
  const open = (r.styleTags.match(/<style /gi) || []).length;
  const close = (r.styleTags.match(/<\/style>/gi) || []).length;
  assert('</style> in rule → split balanced', open === close && open >= 2, `open=${open} close=${close}`);
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
