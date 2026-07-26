#!/usr/bin/env node
// Live smoke test for the canvas-engine image-clone EDIT path.
// Clones a screenshot, then edits the clone and asserts files genuinely changed.
//
// Prereqs: canvas-engine running with the claude CLI logged in (run
//          `claude setup-token` once; no API key needed).
// Usage:   node scripts/smoke-image-edit.mjs [screenshot] [intent]
//   defaults: scripts/fixtures/sample-ui.png + a heading-change intent
//   env:      CANVAS_ENGINE_URL (default http://localhost:3050)
//
// Exits 0 when the edit applies and at least one returned file differs from the
// original clone; 1 otherwise.

import { readFile } from 'node:fs/promises';
import path from 'node:path';

const BASE = process.env.CANVAS_ENGINE_URL ?? 'http://localhost:3050';
const DEFAULT_IMAGE = new URL('./fixtures/sample-ui.png', import.meta.url);
const DEFAULT_INTENT = 'Change the most prominent heading text to "SMOKE TEST OK".';
const MEDIA = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
};

async function readSse(res, onEvent) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split('\n\n');
    buf = parts.pop() ?? '';
    for (const part of parts) {
      const line = part.split('\n').find((l) => l.startsWith('data:'));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()));
      } catch {
        /* ignore non-JSON keepalive lines */
      }
    }
  }
}

async function dataUrlFor(image, argGiven) {
  const ext = path.extname(argGiven ?? 'sample-ui.png').toLowerCase();
  const mediaType = MEDIA[ext];
  if (!mediaType) {
    console.error(`unsupported image extension "${ext}" (use png/jpg/gif/webp)`);
    process.exit(2);
  }
  const b64 = (await readFile(image)).toString('base64');
  return `data:${mediaType};base64,${b64}`;
}

async function clone(dataUrl) {
  const files = new Map();
  let done = null;
  let errored = null;
  const res = await fetch(`${BASE}/clone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: dataUrl }),
  });
  if (!res.ok) {
    console.error(`clone HTTP ${res.status}: ${await res.text()}`);
    process.exit(1);
  }
  await readSse(res, (ev) => {
    if (ev.type === 'status') console.log(`  clone[${ev.phase}] ${ev.message}`);
    else if (ev.type === 'file') files.set(ev.path, ev.content);
    else if (ev.type === 'error') errored = ev;
    else if (ev.type === 'done') done = ev;
  });
  if (errored) {
    console.error(`clone ERROR [${errored.phase}] ${errored.message}`);
    process.exit(1);
  }
  if (!done?.sessionId) {
    console.error('clone: no done event with sessionId');
    process.exit(1);
  }
  return { sessionId: done.sessionId, url: done.url, files };
}

async function edit(sessionId, intent) {
  const files = new Map();
  let done = null;
  let errored = null;
  const res = await fetch(`${BASE}/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, intent }),
  });
  if (!res.ok) {
    console.error(`edit HTTP ${res.status}: ${await res.text()}`);
    process.exit(1);
  }
  await readSse(res, (ev) => {
    if (ev.type === 'status') console.log(`  edit[${ev.phase}] ${ev.message}`);
    else if (ev.type === 'file') files.set(ev.path, ev.content);
    else if (ev.type === 'error') errored = ev;
    else if (ev.type === 'done') done = ev;
  });
  if (errored) {
    console.error(`edit ERROR [${errored.phase}] ${errored.message}`);
    process.exit(1);
  }
  if (!done) {
    console.error('edit: no done event');
    process.exit(1);
  }
  return { done, files };
}

async function main() {
  const imgArg = process.argv[2];
  const intent = process.argv[3] ?? DEFAULT_INTENT;
  const image = imgArg ?? DEFAULT_IMAGE;
  const dataUrl = await dataUrlFor(image, imgArg);

  console.log(`1) clone  ${imgArg ?? 'fixtures/sample-ui.png'}`);
  const cl = await clone(dataUrl);
  console.log(`   -> session ${cl.sessionId} · ${cl.files.size} files · ${cl.url}`);

  console.log(`2) edit   intent="${intent}"`);
  const ed = await edit(cl.sessionId, intent);
  console.log(`   -> outcome ${ed.done.outcome} · ${ed.done.filesChanged.length} file(s) reported`);

  let realChange = false;
  for (const [p, content] of ed.files) {
    if (cl.files.get(p) !== content) {
      realChange = true;
      console.log(`   changed: ${p}`);
    }
  }

  if (ed.done.outcome !== 'applied' || ed.files.size === 0) {
    console.error(`SMOKE FAIL: edit outcome=${ed.done.outcome}, files=${ed.files.size}`);
    process.exit(1);
  }
  if (!realChange) {
    console.error('SMOKE FAIL: edit returned files but none differ from the clone');
    process.exit(1);
  }
  console.log(`SMOKE PASS: clone -> edit applied, files genuinely changed (${cl.url})`);
  process.exit(0);
}

main().catch((e) => {
  console.error('SMOKE FAIL:', e?.message ?? e);
  process.exit(1);
});
