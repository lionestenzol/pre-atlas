// End-to-end pipeline check · feed a real anatomy.json through the full
// canvas-engine consumer side: zod parse → buildPatternRegistry → pickPattern
// → format JSX render. Prints group distribution + per-pattern counts +
// JSX excerpts for spot-check.
//
// Run: cd services/canvas-engine && npx tsx test/e2e-real-capture.mjs

import { readFileSync } from 'node:fs';
import { anatomyV1Schema } from '../src/adapter/v1-schema.ts';
import { buildPatternRegistry, pickPattern } from '../src/pattern-library/index.ts';

const CAPTURES = [
  'C:/Users/bruke/web-audit/.tmp/hn-v1/anatomy.json',
  'C:/Users/bruke/OneDrive/Desktop/anatomy-localhost-c-news-ycombinator-com-1b-moboruxv- (1).json',
  'C:/Users/bruke/web-audit/.canvas/www.figma.com/www.figma.com-zv2v16-mobw1b4l/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/linear.app/linear.app-7o0v19-mod91ex3/anatomy.json',
];

const registry = buildPatternRegistry();
console.log('canvas-engine pattern registry · groups:',
  Array.from(registry.byGroup.keys()).join(', '));
console.log('total patterns:', [...registry.byGroup.values()].reduce((n, arr) => n + arr.length, 0));
console.log();

for (const path of CAPTURES) {
  let raw;
  try {
    raw = JSON.parse(readFileSync(path, 'utf8'));
  } catch (e) {
    console.log(`SKIP ${path}\n  (${e.message})\n`);
    continue;
  }

  // Phase 1 · zod parse (canvas-engine boundary check)
  const result = anatomyV1Schema.safeParse(raw);
  if (!result.success) {
    console.log(`FAIL zod parse · ${path}`);
    console.log(' ', result.error.issues.slice(0, 3).map(i => i.path.join('.') + ': ' + i.message).join(' · '));
    console.log();
    continue;
  }
  const env = result.data;

  // Phase 2 · pickPattern per region
  const groupCounts = {};
  const patternCounts = {};
  const examples = [];
  for (const region of env.regions) {
    const { pattern, group, score } = pickPattern(region, registry);
    groupCounts[group] = (groupCounts[group] || 0) + 1;
    patternCounts[pattern.name] = (patternCounts[pattern.name] || 0) + 1;
    if (examples.length < 3 && group !== 'default') {
      const jsx = pattern.render({
        componentName: 'Region' + region.n,
        region,
        chains: env.chains,
      });
      examples.push({ region: region.name, group, pattern: pattern.name, score, jsxLen: jsx.length, jsxPreview: jsx.split('\n').slice(0, 4).join(' ').slice(0, 140) });
    }
  }

  const cap = path.split(/[\\/]/).slice(-2)[0];
  console.log('─'.repeat(78));
  console.log(`CAPTURE: ${cap}  ·  regions: ${env.regions.length}  ·  chains: ${env.chains.length}`);
  console.log(`zod parse: OK`);
  console.log(`groups:    ${JSON.stringify(groupCounts)}`);
  console.log(`top patterns picked:`);
  for (const [name, count] of Object.entries(patternCounts).sort((a, b) => b[1] - a[1]).slice(0, 6)) {
    console.log(`  ${count.toString().padStart(4)} × ${name}`);
  }
  console.log(`first 3 JSX renders:`);
  for (const ex of examples) {
    console.log(`  - ${ex.pattern} (group=${ex.group}, score=${ex.score}) · "${ex.region}" · ${ex.jsxLen} chars`);
    console.log(`    ${ex.jsxPreview}...`);
  }
  console.log();
}
