#!/usr/bin/env node
// Live smoke test for the canvas-engine image -> code (vision) path.
//
// Prereqs: canvas-engine running with the claude CLI logged in (run
//          `claude setup-token` once; no API key needed).
// Usage:   node scripts/smoke-image-clone.mjs <screenshot.png> [intent]
//   env:   CANVAS_ENGINE_URL  (default http://localhost:3050)
//
// Exits 0 on a clean clone (done event with a url + >=1 file), 1 otherwise.

import { readFile } from 'node:fs/promises';
import path from 'node:path';

const BASE = process.env.CANVAS_ENGINE_URL ?? 'http://localhost:3050';
const MEDIA = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
};

async function main() {
  const DEFAULT_IMAGE = new URL('./fixtures/sample-ui.png', import.meta.url);
  const imgArg = process.argv[2];
  const intent = process.argv[3];
  const image = imgArg ?? DEFAULT_IMAGE;

  const ext = path.extname(imgArg ?? 'sample-ui.png').toLowerCase();
  const mediaType = MEDIA[ext];
  if (!mediaType) {
    console.error(`unsupported image extension "${ext}" (use png/jpg/gif/webp)`);
    process.exit(2);
  }

  const b64 = (await readFile(image)).toString('base64');
  const dataUrl = `data:${mediaType};base64,${b64}`;

  const label = imgArg ?? 'fixtures/sample-ui.png';
  console.log(`POST ${BASE}/clone  (image ${label}, ${(b64.length / 1024).toFixed(0)}KB base64)`);
  const res = await fetch(`${BASE}/clone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: dataUrl, ...(intent ? { intent } : {}) }),
  });

  if (!res.ok) {
    console.error(`HTTP ${res.status}: ${await res.text()}`);
    process.exit(1);
  }

  let done = null;
  let errored = null;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done: rdDone } = await reader.read();
    if (rdDone) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split('\n\n');
    buf = parts.pop() ?? '';
    for (const part of parts) {
      const dataLine = part.split('\n').find((l) => l.startsWith('data:'));
      if (!dataLine) continue;
      let ev;
      try {
        ev = JSON.parse(dataLine.slice(5).trim());
      } catch {
        continue;
      }
      if (ev.type === 'status') console.log(`  [${ev.phase}] ${ev.message}`);
      else if (ev.type === 'file') console.log(`  file: ${ev.path} (${ev.content.length}b)`);
      else if (ev.type === 'error') {
        errored = ev;
        console.error(`  ERROR [${ev.phase}] ${ev.message}`);
      } else if (ev.type === 'done') done = ev;
    }
  }

  if (errored) {
    console.error('SMOKE FAIL: stream emitted an error event');
    process.exit(1);
  }
  if (!done || !done.url || !done.fileCount) {
    console.error(`SMOKE FAIL: no valid done event (${JSON.stringify(done)})`);
    process.exit(1);
  }
  console.log(`SMOKE PASS: ${done.fileCount} files -> ${done.url} (session ${done.sessionId})`);
  process.exit(0);
}

main().catch((e) => {
  console.error('SMOKE FAIL:', e?.message ?? e);
  process.exit(1);
});
