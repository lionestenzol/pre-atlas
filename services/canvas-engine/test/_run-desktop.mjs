import { readFileSync } from 'node:fs';
import { anatomyV1Schema } from '../src/adapter/v1-schema.ts';
import { buildPatternRegistry, pickPattern } from '../src/pattern-library/index.ts';

const FILE = 'C:/Users/bruke/OneDrive/Desktop/anatomy-localhost-c-news-ycombinator-com-1b-moboruxv- (1).json';
const raw = JSON.parse(readFileSync(FILE, 'utf8'));
const env = anatomyV1Schema.safeParse(raw);
if (!env.success) { console.error('FAIL zod:', env.error.issues.slice(0,3)); process.exit(1); }
const data = env.data;
const reg = buildPatternRegistry();

console.log(`Desktop HN capture · ${data.regions.length} regions · ${data.chains.length} chains\n`);

const groups = {}, patterns = {};
for (const r of data.regions) {
  const p = pickPattern(r, reg);
  groups[p.group] = (groups[p.group]||0) + 1;
  patterns[p.pattern.name] = (patterns[p.pattern.name]||0) + 1;
}
console.log('GROUPS:', JSON.stringify(groups));
console.log('TOP PATTERNS:');
for (const [n,c] of Object.entries(patterns).sort((a,b)=>b[1]-a[1]).slice(0,8))
  console.log(`  ${String(c).padStart(4)} × ${n}`);

const sels = data.regions.map(r => r.selector || '');
const idOnly = sels.filter(s => /^#[a-zA-Z_][\w-]*$/.test(s.trim())).length;
const tagId = sels.filter(s => /^[a-z][a-z0-9-]*#[a-zA-Z_][\w-]*$/i.test(s.trim())).length;
const chained = sels.filter(s => s.includes(' > ')).length;
console.log('\nSELECTOR FORMATS:');
console.log(`  id-only (#foo)        ${String(idOnly).padStart(4)}  - OLD format - 0 after re-pull`);
console.log(`  tag#id (a#foo)        ${String(tagId).padStart(4)}  - NEW format from fix`);
console.log(`  chained (a > b > ...) ${String(chained).padStart(4)}  - chain emission`);

console.log('\nSAMPLE RENDERS (one per pattern type):');
const seen = new Set();
let n = 0;
for (const r of data.regions) {
  const p = pickPattern(r, reg);
  if (seen.has(p.pattern.name) || n >= 6) continue;
  seen.add(p.pattern.name);
  const jsx = p.pattern.render({componentName:'R'+r.n, region:r, chains:env.data.chains});
  console.log(`  - ${p.pattern.name} - "${(r.name||'').slice(0,30)}" - score ${p.score}`);
  console.log(`    ${jsx.split('\n').slice(2,4).map(l=>l.trim()).join(' ').slice(0,120)}`);
  n++;
}
