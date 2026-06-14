// canvas-engine · side-effect module: load services/canvas-engine/.env early.
//
// MUST be the first import in server.ts so module-level process.env reads (model,
// ports, backend) see these values.
//
// Two subtleties this handles:
//  1. Host-managed Claude sessions export ANTHROPIC_API_KEY as an EMPTY string.
//     An empty key (a) makes the SDK/CLI 401, and (b) blocks process.loadEnvFile
//     from filling it, because loadEnvFile never overrides an already-present
//     var. So we delete the empty placeholder first, letting a real key from
//     .env (or a normal shell) take effect.
//  2. Everything is fail-soft: no .env (CLI-only / CI) is a normal, valid setup.
//
// Precedence: a non-empty value already in the shell environment always wins
// over .env (loadEnvFile only fills vars that are absent).

import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

if (
  process.env.ANTHROPIC_API_KEY !== undefined &&
  process.env.ANTHROPIC_API_KEY.trim() === ''
) {
  delete process.env.ANTHROPIC_API_KEY;
}

const here = path.dirname(fileURLToPath(import.meta.url));
const envPath = path.resolve(here, '..', '.env');

if (existsSync(envPath)) {
  try {
    process.loadEnvFile(envPath);
  } catch {
    // Malformed or locked .env is non-fatal — shell env still applies.
  }
}
