// Delta SCP · migration runner
//
// Applies the SCP migrations (004 + 005) straight to your database — no manual
// psql step. Idempotent: the migrations use IF NOT EXISTS / OR REPLACE, so it is
// safe to re-run.
//
//   npm run migrate
//
// Needs a Postgres connection string in SUPABASE_DB_URL (or DATABASE_URL). In
// Supabase: Project Settings → Database → Connection string (URI). SSL is
// enabled automatically for non-local hosts.

import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { Client } from 'pg';
import { loadEnvFile } from '../src/env.js';

loadEnvFile();

const MIGRATIONS_DIR = path.resolve(import.meta.dirname, '../../../migrations');

function connectionString(): string {
  const url = process.env.SUPABASE_DB_URL ?? process.env.DATABASE_URL ?? '';
  if (!url) {
    console.error(
      'migrate: set SUPABASE_DB_URL (or DATABASE_URL) to your Postgres connection string.\n' +
        '  Supabase: Project Settings → Database → Connection string (URI).',
    );
    process.exit(1);
  }
  return url;
}

function isLocal(url: string): boolean {
  return /@(localhost|127\.0\.0\.1)[:/]/.test(url) || url.includes('host=/');
}

function scpMigrations(): string[] {
  return readdirSync(MIGRATIONS_DIR)
    .filter((f) => /_scp.*\.sql$/.test(f))
    .sort(); // 004_… before 005_…
}

async function main() {
  const url = connectionString();
  const files = scpMigrations();
  if (files.length === 0) {
    console.error(`migrate: no SCP migrations found in ${MIGRATIONS_DIR}`);
    process.exit(1);
  }

  const client = new Client({
    connectionString: url,
    ssl: isLocal(url) ? undefined : { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    for (const file of files) {
      const sql = readFileSync(path.join(MIGRATIONS_DIR, file), 'utf8');
      await client.query(sql);
      console.log(`[delta-scp] applied ${file}`);
    }
    const { rows } = await client.query(
      `SELECT to_regclass('scp_jobs') IS NOT NULL AS table_ok,
              (SELECT count(*) FROM pg_proc
                WHERE proname IN ('claim_scp_job','reap_stale_scp_jobs')) AS fn_count`,
    );
    console.log(
      `[delta-scp] schema ready: scp_jobs=${rows[0].table_ok} functions=${rows[0].fn_count}/2`,
    );
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error('[delta-scp] migrate failed:', err instanceof Error ? err.message : err);
  process.exit(1);
});
