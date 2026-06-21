// Delta SCP · runtime configuration (env-driven, with sane defaults)

import os from 'node:os';
import path from 'node:path';
import { loadEnvFile } from './env.js';

export interface ScpConfig {
  supabaseUrl: string;
  supabaseServiceKey: string;
  port: number;
  pollIntervalMs: number;
  cloneDir: string;
  maxFileBytes: number;
  // Worker reaper
  reapTimeoutMs: number; // a 'processing' job older than this is orphaned
  reapIntervalMs: number; // how often the worker runs the reaper
  // API gateway auth
  apiKey: string; // required to mutate/read jobs; empty disables the gateway
  // Repo-fetch guardrails
  allowedHosts: string[]; // empty = any public host allowed
  allowLocal: boolean; // permit local paths / file:// (off by default)
  maxFiles: number; // abort a repo that walks past this many source files
  maxTotalBytes: number; // abort a repo whose scanned source exceeds this
  // The flue: where rendered Markdown drops are written for the Chainer/droplist.
  flueDir: string;
  // Worker auto-populates the AST graph (migration 006) after each job. Fail-soft.
  graphAutoPopulate: boolean;
}

function num(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

// Integer within [min, max]; out-of-range or non-finite values fall back to the
// default so a stray `SCP_POLL_INTERVAL_MS=0` can't wedge the worker.
function intInRange(name: string, fallback: number, min: number, max = Number.MAX_SAFE_INTEGER): number {
  const value = Math.trunc(num(name, fallback));
  return value >= min && value <= max ? value : fallback;
}

function bool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined) return fallback;
  return /^(1|true|yes|on)$/i.test(raw.trim());
}

function list(name: string): string[] {
  return (process.env[name] ?? '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

export function loadConfig(): ScpConfig {
  loadEnvFile(); // pick up a local .env on first load
  return {
    supabaseUrl: process.env.SUPABASE_URL ?? '',
    supabaseServiceKey: process.env.SUPABASE_SERVICE_KEY ?? '',
    port: intInRange('SCP_PORT', 3012, 1, 65535),
    pollIntervalMs: intInRange('SCP_POLL_INTERVAL_MS', 5000, 1),
    // Portable default: an absolute, drive-qualified temp path on every OS.
    // A hardcoded '/tmp/...' becomes the drive-relative '\tmp\...' on Windows,
    // which breaks git clone (see source.ts cloneRepo). os.tmpdir() avoids that.
    cloneDir: process.env.SCP_CLONE_DIR ?? path.join(os.tmpdir(), 'delta-scp'),
    maxFileBytes: intInRange('SCP_MAX_FILE_BYTES', 1024 * 1024, 1),
    reapTimeoutMs: intInRange('SCP_REAP_TIMEOUT_MS', 10 * 60 * 1000, 1000),
    reapIntervalMs: intInRange('SCP_REAP_INTERVAL_MS', 60 * 1000, 1000),
    apiKey: process.env.SCP_API_KEY ?? '',
    allowedHosts: list('SCP_ALLOWED_HOSTS'),
    allowLocal: bool('SCP_ALLOW_LOCAL', false),
    maxFiles: intInRange('SCP_MAX_FILES', 20000, 1),
    maxTotalBytes: intInRange('SCP_MAX_TOTAL_BYTES', 50 * 1024 * 1024, 1),
    // Default to a local outbox in the service dir — loose, explicit coupling to
    // droplist (point SCP_FLUE_DIR at droplist's watched inbox to wire them up).
    flueDir: process.env.SCP_FLUE_DIR ?? path.join(process.cwd(), 'flue-out'),
    graphAutoPopulate: bool('SCP_GRAPH_AUTOPOPULATE', true),
  };
}

/** Throws with a clear message if Supabase credentials are missing. */
export function requireSupabase(config: ScpConfig): void {
  const missing: string[] = [];
  if (!config.supabaseUrl) missing.push('SUPABASE_URL');
  if (!config.supabaseServiceKey) missing.push('SUPABASE_SERVICE_KEY');
  if (missing.length > 0) {
    throw new Error(
      `Delta SCP: missing required env var(s): ${missing.join(', ')}. ` +
        'Copy .env.example to .env and fill in your Supabase project values.',
    );
  }
}
