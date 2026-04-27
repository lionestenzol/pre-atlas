// Trainer · grade canvas-engine pattern picker against leaf-tag ground truth.
//
// "Truth" = the tag at the end of region.selector (a, button, h2, header...).
// The browser writes that tag · the cascade did not · so it's an independent
// label we can grade the picker against without trusting the producer.
//
// CODEX-AUDIT-NOTE (2026-04-26): the previous version mixed deterministic
// tag→pattern truth with heuristic acceptable-sets for stylistic variants,
// which made the sub-pattern accuracy score partially circular (the truth
// function copied the picker's policy). This version splits cleanly:
//
//   STRICT REPORT     · only tags whose leaf uniquely determines a pattern
//                       (header → landmark/header, h1 → heading/hero, etc).
//                       This is the rigorous truth metric.
//
//   HEURISTIC REPORT  · for stylistic-variant tags (a, button, h2-6, ul, ol,
//                       form, input, article) where multiple patterns are
//                       valid. Reported as opinion-vs-opinion · NOT a truth
//                       metric · useful for surfacing confusion buckets.
//
// Run: cd services/canvas-engine && npx tsx test/trainer-vs-truth.mjs

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { anatomyV1Schema } from '../src/adapter/v1-schema.ts';
import { buildPatternRegistry, pickPattern } from '../src/pattern-library/index.ts';

const CAPTURE_ROOTS = [
  'C:/Users/bruke/web-audit/.tmp',
  'C:/Users/bruke/web-audit/.canvas',
  'C:/Users/bruke/Pre Atlas/.tmp',
];
const EXTRA_FILES = [
  'C:/Users/bruke/OneDrive/Desktop/anatomy-localhost-c-news-ycombinator-com-1b-moboruxv- (1).json',
];

// === DETERMINISTIC TRUTH ===
// Group truth: leaf tag uniquely identifies the canvas-engine group.
const TAG_TO_GROUP = {
  a: 'clickable', button: 'clickable',
  h1: 'heading', h2: 'heading', h3: 'heading',
  h4: 'heading', h5: 'heading', h6: 'heading',
  header: 'landmark', nav: 'landmark', aside: 'landmark',
  footer: 'landmark', main: 'landmark', section: 'landmark',
  form: 'form', textarea: 'form', select: 'form', input: 'form',
  ul: 'list', ol: 'list',
  article: 'card',
};

// Strict pattern truth: leaf tag uniquely identifies the sub-pattern with no
// further signals required. Only landmarks + h1 qualify · everything else has
// stylistic variants that need bounds/text/desc heuristics to disambiguate.
const TAG_TO_PATTERN_STRICT = {
  header: 'landmark/header',
  nav: 'landmark/nav',
  footer: 'landmark/footer',
  aside: 'landmark/aside',
  section: 'landmark/section',
  main: 'landmark/section',
  h1: 'heading/hero',
};

// === HEURISTIC ACCEPTANCE ===
// For stylistic-variant tags. Returns a Set of "plausible" patterns based on
// non-tag signals (bounds, name shape, desc, fetches). NOT ground truth.
const CTA_RE = /\b(subscribe|sign\s?up|get\s?started|start\s?now|try\s?(it\s)?free|join|buy\s?now|download|install|get\s?the\s?app|book\s?a\s?demo)\b/i;

function heuristicAcceptable(region, tag) {
  const w = region.bounds?.w ?? 0;
  const h = region.bounds?.h ?? 0;
  const name = (region.name || '').trim();
  const nameL = name.toLowerCase();
  const compact = w > 0 && w >= 40 && w <= 150 && h > 0 && h < 36;
  const iconSize = w > 0 && w < 48 && h > 0 && h < 48 && name.length <= 4;
  const tagLikeText = name.length > 0 && (name.length <= 8 || /^[\d+\-*#%]+$/.test(name));

  // h2-h6 · tagged is default, eyebrow when desc present
  if (/^h[2-6]$/.test(tag)) return new Set(['heading/tagged', 'heading/eyebrow']);

  // a · link is default, with stylistic variants when bounds/name suggest
  if (tag === 'a') {
    if (iconSize) return new Set(['clickable/icon-button']);
    if (CTA_RE.test(nameL) && (w > 200 || h > 50)) return new Set(['clickable/cta']);
    const out = new Set(['clickable/link']);
    if (compact && tagLikeText) out.add('clickable/pill');
    if (CTA_RE.test(nameL)) out.add('clickable/cta');
    return out;
  }

  if (tag === 'button') {
    if (iconSize) return new Set(['clickable/icon-button']);
    if (CTA_RE.test(nameL) && (w > 200 || h > 50)) return new Set(['clickable/cta']);
    const out = new Set(['clickable/button']);
    if (compact && tagLikeText) out.add('clickable/pill');
    if (CTA_RE.test(nameL)) out.add('clickable/cta');
    return out;
  }

  if (tag === 'form' || tag === 'input' || tag === 'textarea' || tag === 'select') {
    if (nameL.includes('search')) return new Set(['form/inline', 'form/stacked']);
    if (nameL.includes('subscribe') || nameL.includes('newsletter')) return new Set(['form/newsletter', 'form/stacked']);
    return new Set(['form/stacked', 'form/inline']);
  }

  if (tag === 'ul' || tag === 'ol') {
    if (w > 600) return new Set(['list/grid', 'list/vertical']);
    if (h > 200) return new Set(['list/vertical', 'list/grid']);
    return new Set(['list/tags', 'list/vertical']);
  }

  if (tag === 'article') {
    const out = new Set(['card/content']);
    if (region.fetches?.length) out.add('card/action');
    if (/^\d+/.test(name)) out.add('card/stat');
    return out;
  }

  return null;
}

// === HELPERS ===
const LEAF_RE = /\>\s*([a-zA-Z][a-zA-Z0-9-]*)(?:[:.\[#]|$)/g;
function leafTag(selector) {
  if (!selector) return null;
  let last = null;
  for (const m of selector.matchAll(LEAF_RE)) last = m[1].toLowerCase();
  return last;
}

function* walkAnatomyFiles(dir) {
  let entries;
  try { entries = readdirSync(dir); } catch { return; }
  for (const name of entries) {
    const full = join(dir, name);
    let s;
    try { s = statSync(full); } catch { continue; }
    if (s.isDirectory()) yield* walkAnatomyFiles(full);
    else if (name === 'anatomy.json') yield full;
  }
}

function findCaptures() {
  const out = [];
  for (const root of CAPTURE_ROOTS) for (const fp of walkAnatomyFiles(root)) out.push(fp);
  for (const fp of EXTRA_FILES) { try { statSync(fp); out.push(fp); } catch {} }
  return out;
}

function bar(value, max, width = 40) {
  const fill = max > 0 ? Math.round(width * value / max) : 0;
  return '█'.repeat(fill) + '·'.repeat(width - fill);
}

function pct(num, den) {
  return den > 0 ? (100 * num / den).toFixed(1) : '0.0';
}

// === MAIN ===
function main() {
  const registry = buildPatternRegistry();
  const captures = findCaptures();
  console.log(`Loaded ${captures.length} captures from disk.\n`);

  // group-level (deterministic)
  let total = 0, gDecidable = 0, gCorrect = 0;
  const groupStats = {};

  // STRICT pattern-level (deterministic single-answer)
  let sDecidable = 0, sCorrect = 0;
  const strictMistakes = new Map();    // (tag, picked) → count
  const strictSamples = new Map();      // key → samples

  // HEURISTIC pattern-level (multi-answer acceptance set)
  let hDecidable = 0, hAccepted = 0;
  const heuristicMistakes = new Map();
  const heuristicSamples = new Map();

  for (const fp of captures) {
    let raw;
    try { raw = JSON.parse(readFileSync(fp, 'utf8')); } catch { continue; }
    const r = anatomyV1Schema.safeParse(raw);
    if (!r.success) continue;
    const env = r.data;
    const cap = (fp.split(/[\\/]/).slice(-2)[0] || '').slice(0, 30);

    for (const region of env.regions) {
      total++;
      const tag = leafTag(region.selector);
      const truthGroup = tag ? TAG_TO_GROUP[tag] : null;
      if (!truthGroup) continue;

      const pick = pickPattern(region, registry);

      // group grading
      gDecidable++;
      const groupOk = pick.group === truthGroup;
      if (groupOk) gCorrect++;
      groupStats[truthGroup] = groupStats[truthGroup] || { total: 0, correct: 0 };
      groupStats[truthGroup].total++;
      if (groupOk) groupStats[truthGroup].correct++;

      // STRICT pattern grading · only for unambiguous-tag regions
      const strictTruth = TAG_TO_PATTERN_STRICT[tag];
      if (strictTruth) {
        sDecidable++;
        const ok = pick.pattern.name === strictTruth;
        if (ok) sCorrect++;
        if (!ok) {
          const key = `<${tag}> picked ${pick.pattern.name} · expected ${strictTruth}`;
          strictMistakes.set(`${tag}|${pick.pattern.name}`, (strictMistakes.get(`${tag}|${pick.pattern.name}`) ?? 0) + 1);
          if (!strictSamples.has(key)) strictSamples.set(key, []);
          const samples = strictSamples.get(key);
          if (samples.length < 5) samples.push({ cap, name: region.name, bounds: region.bounds && `${Math.round(region.bounds.w)}x${Math.round(region.bounds.h)}`, score: pick.score });
        }
      } else {
        // HEURISTIC pattern grading · for stylistic-variant tags
        const accept = heuristicAcceptable(region, tag);
        if (accept) {
          hDecidable++;
          const ok = accept.has(pick.pattern.name);
          if (ok) hAccepted++;
          if (!ok) {
            const expected = [...accept].join(' | ');
            const key = `<${tag}> picked ${pick.pattern.name}`;
            heuristicMistakes.set(`${tag}|${pick.pattern.name}`, (heuristicMistakes.get(`${tag}|${pick.pattern.name}`) ?? 0) + 1);
            if (!heuristicSamples.has(key)) heuristicSamples.set(key, { expected, samples: [] });
            const slot = heuristicSamples.get(key);
            if (slot.samples.length < 5) slot.samples.push({ cap, name: region.name, bounds: region.bounds && `${Math.round(region.bounds.w)}x${Math.round(region.bounds.h)}`, score: pick.score });
          }
        }
      }
    }
  }

  // === REPORTS ===
  console.log('='.repeat(78));
  console.log('GROUP-LEVEL ACCURACY  (deterministic · leaf tag determines group)');
  console.log('='.repeat(78));
  console.log(`Decidable: ${gDecidable} / ${total}    Correct: ${gCorrect} / ${gDecidable} = ${pct(gCorrect, gDecidable)}%\n`);
  for (const [g, s] of Object.entries(groupStats).sort((a,b)=>b[1].total-a[1].total)) {
    const p = pct(s.correct, s.total).padStart(5);
    console.log(`  ${g.padEnd(10)} ${p}%  ${bar(s.correct, s.total)}  (${s.correct}/${s.total})`);
  }

  console.log();
  console.log('='.repeat(78));
  console.log('STRICT PATTERN ACCURACY  (deterministic · single answer per tag)');
  console.log('='.repeat(78));
  console.log(`Tags counted: ${Object.keys(TAG_TO_PATTERN_STRICT).join(', ')}`);
  console.log(`Decidable: ${sDecidable}    Correct: ${sCorrect} / ${sDecidable} = ${pct(sCorrect, sDecidable)}%\n`);
  if (strictMistakes.size === 0) {
    console.log('  no mistakes.');
  } else {
    for (const [k, c] of [...strictMistakes.entries()].sort((a,b)=>b[1]-a[1])) {
      const [tag, picked] = k.split('|');
      console.log(`  ${String(c).padStart(4)} × <${tag}> picked ${picked}`);
    }
    console.log();
    console.log('Samples:');
    for (const [key, samples] of [...strictSamples.entries()].sort()) {
      console.log(`\n  ${key}`);
      for (const s of samples.slice(0, 3)) {
        console.log(`    · "${(s.name || '').slice(0, 32)}" bounds=${s.bounds || '?'} (score ${s.score})`);
      }
    }
  }

  console.log();
  console.log('='.repeat(78));
  console.log('HEURISTIC PATTERN REPORT  (stylistic variants · NOT a truth metric)');
  console.log('='.repeat(78));
  console.log('This section grades sub-pattern picks for tags where multiple patterns');
  console.log('are stylistically valid (a, button, h2-6, ul, ol, form, input, article).');
  console.log('Reported as opinion-vs-opinion · use only to surface confusion buckets.\n');
  console.log(`Decidable: ${hDecidable}    In-acceptable-set: ${hAccepted} / ${hDecidable} = ${pct(hAccepted, hDecidable)}%`);
  if (heuristicMistakes.size > 0) {
    console.log();
    console.log('Picks outside the heuristic acceptable set:');
    for (const [k, c] of [...heuristicMistakes.entries()].sort((a,b)=>b[1]-a[1])) {
      const [tag, picked] = k.split('|');
      console.log(`  ${String(c).padStart(4)} × <${tag}> picked ${picked}`);
    }
    console.log();
    console.log('Samples (first 3 per bucket):');
    for (const [key, slot] of [...heuristicSamples.entries()].sort()) {
      console.log(`\n  ${key}`);
      console.log(`    heuristic-expected: ${slot.expected}`);
      for (const s of slot.samples.slice(0, 3)) {
        console.log(`      · "${(s.name || '').slice(0, 36)}" bounds=${s.bounds || '?'} (score ${s.score})`);
      }
    }
  }

  console.log();
  console.log('='.repeat(78));
  console.log('SUMMARY');
  console.log('='.repeat(78));
  console.log(`  group truth         · ${pct(gCorrect, gDecidable).padStart(6)}%   (${gCorrect}/${gDecidable})  · rigorous`);
  console.log(`  strict pattern truth · ${pct(sCorrect, sDecidable).padStart(6)}%   (${sCorrect}/${sDecidable})   · rigorous`);
  console.log(`  heuristic pattern    · ${pct(hAccepted, hDecidable).padStart(6)}%   (${hAccepted}/${hDecidable}) · informational only`);
  console.log('='.repeat(78));
}

main();
