// Unit-test the dwell-detection algorithm extracted from anatomy-extension.
// Synthesizes 3 cursor patterns and verifies which dwells fire.
const WATCH_MIN_DWELL_MS = 450;
const WATCH_MAX_DWELL_MS = 2600;
const WATCH_MOVE_THRESHOLD = 0.02;

function detectDwellRuns(samples, vw, vh) {
  if (samples.length < 2) return [];
  const diag = Math.hypot(vw, vh) || 1;
  const dwells = [];
  let runStart = 0;
  function flushIfDwell(startIdx, endIdxExcl) {
    if (endIdxExcl - startIdx < 2) return;
    const a = samples[startIdx], b = samples[endIdxExcl - 1];
    const dur = b.t - a.t;
    if (dur < WATCH_MIN_DWELL_MS || dur > WATCH_MAX_DWELL_MS) return;
    const slice = samples.slice(startIdx, endIdxExcl);
    const ax = slice.reduce((s, p) => s + p.x, 0) / slice.length;
    const ay = slice.reduce((s, p) => s + p.y, 0) / slice.length;
    dwells.push({ x: Math.round(ax), y: Math.round(ay), durationMs: dur });
  }
  for (let i = 1; i < samples.length; i++) {
    const prev = samples[i - 1], cur = samples[i];
    const dist = Math.hypot(cur.x - prev.x, cur.y - prev.y) / diag;
    if (dist > WATCH_MOVE_THRESHOLD) {
      flushIfDwell(runStart, i);
      runStart = i;
    }
  }
  flushIfDwell(runStart, samples.length);
  return dwells;
}

const VW = 1280, VH = 800;

// Pattern A: dwell at (200,300) for 1000ms, jump to (900,600), dwell 800ms, jump back, dwell 200ms (too short).
function build() {
  const samples = [];
  let t = 0;
  // Dwell A: 1000ms at (200,300) jittering ±2px
  for (let i = 0; i < 20; i++) { samples.push({ t: t, x: 200 + (i % 3 - 1) * 2, y: 300 + (i % 5 - 2) * 2 }); t += 50; }
  // Jump to (900,600) — a single big move
  samples.push({ t: t, x: 900, y: 600 }); t += 50;
  // Dwell B: 800ms at (900,600)
  for (let i = 0; i < 16; i++) { samples.push({ t: t, x: 900 + (i % 3 - 1) * 2, y: 600 + (i % 5 - 2) * 2 }); t += 50; }
  // Jump to (200,300)
  samples.push({ t: t, x: 200, y: 300 }); t += 50;
  // Dwell C (too short): 200ms
  for (let i = 0; i < 4; i++) { samples.push({ t: t, x: 200, y: 300 }); t += 50; }
  return samples;
}

const samples = build();
const dwells = detectDwellRuns(samples, VW, VH);

console.log('input samples:', samples.length);
console.log('detected dwells:', dwells.length);
console.log(JSON.stringify(dwells, null, 2));

// Assertions
const expected = 2; // A and B; C is too short
if (dwells.length !== expected) {
  console.error('\nFAIL: expected ' + expected + ' dwells, got ' + dwells.length);
  process.exit(1);
}
const [d1, d2] = dwells;
if (Math.abs(d1.x - 200) > 5 || Math.abs(d1.y - 300) > 5) {
  console.error('FAIL: dwell #1 center off — got (' + d1.x + ',' + d1.y + ')');
  process.exit(1);
}
if (Math.abs(d2.x - 900) > 5 || Math.abs(d2.y - 600) > 5) {
  console.error('FAIL: dwell #2 center off — got (' + d2.x + ',' + d2.y + ')');
  process.exit(1);
}
if (d1.durationMs < WATCH_MIN_DWELL_MS || d1.durationMs > WATCH_MAX_DWELL_MS) {
  console.error('FAIL: dwell #1 duration out of band');
  process.exit(1);
}
console.log('\nPASS · 2 dwells detected, centers match expected, 200ms dwell correctly skipped');
