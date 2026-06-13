// Delta SCP · runtime configuration (env-driven, with sane defaults)

export interface ScpConfig {
  supabaseUrl: string;
  supabaseServiceKey: string;
  port: number;
  pollIntervalMs: number;
  cloneDir: string;
  maxFileBytes: number;
}

function num(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function loadConfig(): ScpConfig {
  return {
    supabaseUrl: process.env.SUPABASE_URL ?? '',
    supabaseServiceKey: process.env.SUPABASE_SERVICE_KEY ?? '',
    port: num('SCP_PORT', 3012),
    pollIntervalMs: num('SCP_POLL_INTERVAL_MS', 5000),
    cloneDir: process.env.SCP_CLONE_DIR ?? '/tmp/delta-scp',
    maxFileBytes: num('SCP_MAX_FILE_BYTES', 1024 * 1024),
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
