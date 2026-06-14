// Delta SCP · zero-dependency .env loader
//
// Loads a local .env into process.env so the service "just works" once you drop
// your credentials on disk — no dotenv dependency, no manual `export`s. Existing
// environment variables always win (the shell/host overrides the file).

import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

let loaded = false;

/** Parse a minimal .env (KEY=VALUE, # comments, optional quotes, `export `). */
function parse(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const body = line.startsWith('export ') ? line.slice(7) : line;
    const eq = body.indexOf('=');
    if (eq === -1) continue;
    const key = body.slice(0, eq).trim();
    let val = body.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    if (key) out[key] = val;
  }
  return out;
}

/**
 * Load `.env` from the given dir (default: the service root) once. Variables
 * already present in process.env are left untouched.
 */
export function loadEnvFile(dir: string = path.resolve(import.meta.dirname, '..')): void {
  if (loaded) return;
  loaded = true;
  const file = process.env.SCP_ENV_FILE ?? path.join(dir, '.env');
  if (!existsSync(file)) return;
  for (const [k, v] of Object.entries(parse(readFileSync(file, 'utf8')))) {
    if (process.env[k] === undefined) process.env[k] = v;
  }
}
