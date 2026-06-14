// Delta SCP · DB integration tests
//
// Exercises the concurrency-critical SQL layer (migrations 004 + 005) against a
// real Postgres: the atomic claim function and the stale-job reaper. The
// supabase-js wrappers in src/queue.ts are thin pass-throughs over these, so
// proving the SQL correct proves the queue's hard parts.
//
// Self-contained: spins up a throwaway Postgres cluster in a temp dir. Skips
// cleanly when Postgres server binaries are unavailable (e.g. minimal CI).

import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from 'pg';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// ---- locate Postgres server binaries -------------------------------------

function findPgBin(): string | null {
  // Honour an explicit override, then PATH, then the Debian layout.
  if (process.env.PGBIN && existsSync(path.join(process.env.PGBIN, 'initdb'))) {
    return process.env.PGBIN;
  }
  try {
    const p = execFileSync('which', ['initdb'], { encoding: 'utf8' }).trim();
    if (p) return path.dirname(p);
  } catch {
    /* not on PATH */
  }
  for (const v of ['16', '15', '14', '13']) {
    const dir = `/usr/lib/postgresql/${v}/bin`;
    if (existsSync(path.join(dir, 'initdb'))) return dir;
  }
  return null;
}

const PG_BIN = findPgBin();
// Postgres refuses to run as root; when we are root, drive it as the postgres user.
const RUN_AS_POSTGRES = process.getuid?.() === 0 && hasPostgresUser();

function hasPostgresUser(): boolean {
  return spawnSync('id', ['postgres']).status === 0;
}

const CAN_RUN = PG_BIN !== null && (process.getuid?.() !== 0 || RUN_AS_POSTGRES);

// ---- temp cluster lifecycle ----------------------------------------------

const MIGRATIONS = path.resolve(HERE, '../../../migrations');
let dataDir = '';
let sockDir = '';
let client: Client;

function run(bin: string, args: string[]): void {
  // Run as the postgres user when we are root, otherwise directly.
  const res = RUN_AS_POSTGRES
    ? spawnSync('runuser', ['-u', 'postgres', '--', path.join(PG_BIN!, bin), ...args], {
        encoding: 'utf8',
      })
    : spawnSync(path.join(PG_BIN!, bin), args, { encoding: 'utf8' });
  if (res.status !== 0) {
    throw new Error(`${bin} failed: ${res.stderr || res.stdout}`);
  }
}

async function applyMigration(file: string): Promise<void> {
  const sql = readFileSync(path.join(MIGRATIONS, file), 'utf8');
  await client.query(sql);
}

beforeAll(async () => {
  if (!CAN_RUN) return;

  const base = mkdtempSync(path.join(tmpdir(), 'scp-pg-'));
  dataDir = path.join(base, 'data');
  sockDir = path.join(base, 'sock');
  execFileSync('mkdir', ['-p', dataDir, sockDir]);
  if (RUN_AS_POSTGRES) {
    // postgres user must own the whole tree it reads/writes.
    execFileSync('chown', ['-R', 'postgres:postgres', base]);
  }

  run('initdb', ['-D', dataDir, '-U', 'postgres', '--auth=trust', '--no-sync']);
  // Listen only on a unix socket in our temp dir — no TCP, no port clashes.
  // -l redirects the postmaster's output to a logfile; without it the daemon
  // inherits run()'s stdio pipes and holds them open, so spawnSync would block
  // forever waiting for EOF even after pg_ctl itself exits.
  run('pg_ctl', [
    '-D', dataDir,
    '-l', path.join(base, 'pg.log'),
    '-o', `-c listen_addresses='' -c unix_socket_directories='${sockDir}'`,
    '-w', '-t', '30', 'start',
  ]);

  client = new Client({ host: sockDir, user: 'postgres', database: 'postgres' });
  await client.connect();
  await applyMigration('004_scp_compression_queue.sql');
  await applyMigration('005_scp_reaper.sql');
}, 60_000);

afterAll(async () => {
  if (!CAN_RUN) return;
  await client?.end().catch(() => {});
  try {
    run('pg_ctl', ['-D', dataDir, '-m', 'immediate', 'stop']);
  } catch {
    /* best effort */
  }
  if (dataDir) rmSync(path.dirname(dataDir), { recursive: true, force: true });
});

// ---- tests ---------------------------------------------------------------

const d = CAN_RUN ? describe : describe.skip;

d('claim_scp_job() concurrency', () => {
  it('never hands the same job to two workers', async () => {
    await client.query('TRUNCATE scp_jobs');
    const total = 5;
    for (let i = 0; i < total; i++) {
      await client.query('INSERT INTO scp_jobs (repo_url) VALUES ($1)', [
        `https://example.com/repo-${i}.git`,
      ]);
    }

    // Fire more concurrent claims than there are jobs, each on its own client.
    const workers = 8;
    const clients = await Promise.all(
      Array.from({ length: workers }, async () => {
        const c = new Client({ host: sockDir, user: 'postgres', database: 'postgres' });
        await c.connect();
        return c;
      }),
    );
    try {
      const results = await Promise.all(
        clients.map((c) => c.query('SELECT * FROM claim_scp_job()')),
      );
      const claimed = results.flatMap((r) => r.rows);
      const ids = claimed.map((row) => row.id);

      expect(claimed).toHaveLength(total); // exactly the available jobs
      expect(new Set(ids).size).toBe(total); // all distinct — no double-claim
      for (const row of claimed) {
        expect(row.status).toBe('processing');
        expect(row.attempt).toBe(1);
        expect(row.claimed_at).not.toBeNull();
      }
    } finally {
      await Promise.all(clients.map((c) => c.end()));
    }

    // Queue is now drained; a further claim returns nothing (no crash).
    const empty = await client.query('SELECT * FROM claim_scp_job()');
    expect(empty.rows).toHaveLength(0);
  });
});

d('reap_stale_scp_jobs()', () => {
  it('re-queues orphans, errors out exhausted ones, leaves fresh ones', async () => {
    await client.query('TRUNCATE scp_jobs');

    // Orphan with attempts left -> back to pending.
    const requeue = await client.query(
      `INSERT INTO scp_jobs (repo_url, status, attempt, max_attempts, claimed_at)
       VALUES ('https://x/a.git', 'processing', 1, 3, NOW() - INTERVAL '1 hour')
       RETURNING id`,
    );
    // Orphan with no attempts left -> error.
    const exhausted = await client.query(
      `INSERT INTO scp_jobs (repo_url, status, attempt, max_attempts, claimed_at)
       VALUES ('https://x/b.git', 'processing', 3, 3, NOW() - INTERVAL '1 hour')
       RETURNING id`,
    );
    // Freshly claimed -> untouched.
    const fresh = await client.query(
      `INSERT INTO scp_jobs (repo_url, status, attempt, max_attempts, claimed_at)
       VALUES ('https://x/c.git', 'processing', 1, 3, NOW())
       RETURNING id`,
    );

    const reaped = await client.query('SELECT * FROM reap_stale_scp_jobs($1)', [60]);
    expect(reaped.rows).toHaveLength(2);

    const byId = async (id: string) =>
      (await client.query('SELECT * FROM scp_jobs WHERE id = $1', [id])).rows[0];

    const a = await byId(requeue.rows[0].id);
    expect(a.status).toBe('pending');
    expect(a.claimed_at).toBeNull();

    const b = await byId(exhausted.rows[0].id);
    expect(b.status).toBe('error');
    expect(b.error_log).toContain('[reaper]');

    const c = await byId(fresh.rows[0].id);
    expect(c.status).toBe('processing'); // not stale yet
  });
});
