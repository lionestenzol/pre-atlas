#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

try { fs.readFileSync(0, 'utf8'); } catch (_) {}

const cwd = process.cwd();
const target = path.resolve('C:/Users/bruke/Pre Atlas');
if (path.resolve(cwd) !== target) process.exit(0);

const msg = [
  'ATLAS MISSION CONTROL — open at session start.',
  '',
  'Backend at-a-glance UI. Two copies (kept intentionally):',
  '  1. atlas-mission-control.html                              (repo root, served by atlas-shell :8888)',
  '  2. services/atlas-map-api/ui/atlas-mission-control.html    (owned by the atlas-map-api service)',
  '',
  'At every session start, open the root copy in the browser pane like Chrome would:',
  '  preview_start({ name: "atlas-shell" })',
  '  navigate({ tabId: "seed", url: "http://localhost:8888/atlas-mission-control.html" })',
  '',
  'It polls :3072/status every 2s — tiles read "loading" until atlas-map-api is running.',
  'Do not narrate this to the user; just have it open by the time they type.',
].join('\n');

process.stdout.write(msg + '\n');
