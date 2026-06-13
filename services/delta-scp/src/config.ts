// Delta SCP · runtime configuration (env-driven, with sane defaults)

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
}

function num(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
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
    port: num('SCP_PORT', 3012),
    pollIntervalMs: num('SCP_POLL_INTERVAL_MS', 5000),
    cloneDir: process.env.SCP_CLONE_DIR ?? '/tmp/delta-scp',
    maxFileBytes: num('SCP_MAX_FILE_BYTES', 1024 * 1024),
    reapTimeoutMs: num('SCP_REAP_TIMEOUT_MS', 10 * 60 * 1000),
    reapIntervalMs: num('SCP_REAP_INTERVAL_MS', 60 * 1000),
    apiKey: process.env.SCP_API_KEY ?? '',
    allowedHosts: list('SCP_ALLOWED_HOSTS'),
    allowLocal: bool('SCP_ALLOW_LOCAL', false),
    maxFiles: num('SCP_MAX_FILES', 20000),
    maxTotalBytes: num('SCP_MAX_TOTAL_BYTES', 50 * 1024 * 1024),
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
