// Delta SCP · worker — the core agentic loop
//
// Fixes over a naive setInterval(poll, 5000) queue:
//   1. Atomic claim (claim_scp_job RPC) — no two workers grab the same job.
//   2. Drains the queue back-to-back, then idles one poll interval — no fixed
//      5s ceiling on throughput.
//   3. A single self-rescheduling timer — runs never overlap, even if a job
//      takes longer than the poll interval.
//   4. Failures re-queue with attempt accounting instead of being lost.

import type { SupabaseClient } from '@supabase/supabase-js';
import { loadConfig, type ScpConfig } from './config.js';
import { getSupabase } from './supabase.js';
import { claimNextJob, completeJob, failJob, reapStaleJobs } from './queue.js';
import { fetchSourceFiles } from './source.js';
import { compressTree } from './compressor.js';
import { buildGraphRows, persistGraph } from './graph.js';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Strip credentials and query/fragment from a URL before it hits the logs. */
function redactRepoUrl(input: string): string {
  try {
    const u = new URL(input);
    u.username = '';
    u.password = '';
    u.search = '';
    u.hash = '';
    return u.toString();
  } catch {
    return '<non-url repo path>';
  }
}

/**
 * Auto-populate the AST graph (migration 006) from a job's source files.
 * Fail-soft: the graph is a secondary index, so a missing migration or a DB
 * hiccup is logged and swallowed — it must never fail an already-complete job.
 */
async function populateGraph(
  db: SupabaseClient,
  repoUrl: string,
  files: { path: string; content: string }[],
): Promise<void> {
  try {
    const rows = buildGraphRows(repoUrl, files);
    const { nodes, edges } = await persistGraph(db, repoUrl, rows);
    console.log(`[delta-scp] graph populated · ${nodes} nodes · ${edges} edges`);
  } catch (err) {
    console.error('[delta-scp] graph populate failed (non-fatal):', err);
  }
}

/** Process exactly one job if available. Returns true if a job was handled. */
export async function tick(db: SupabaseClient, config: ScpConfig): Promise<boolean> {
  const job = await claimNextJob(db);
  if (!job) return false;

  console.log(
    `[delta-scp] claimed job ${job.id} (attempt ${job.attempt}) · ${redactRepoUrl(job.repo_url)}`,
  );
  try {
    // One fetch feeds both compression and graph population.
    const files = await fetchSourceFiles(job.repo_url, config);
    const compressed = compressTree(job.repo_url, files, new Date().toISOString());
    await completeJob(db, job, compressed);
    console.log(
      `[delta-scp] complete ${job.id} · ${compressed.stats.files_included} files · ` +
        `token_yield=${compressed.stats.token_yield}`,
    );
    // Secondary index, after the job is durably complete.
    if (config.graphAutoPopulate) {
      await populateGraph(db, job.repo_url, files);
    }
  } catch (err) {
    await failJob(db, job, err);
    console.error(`[delta-scp] failed ${job.id}:`, err);
  }
  return true;
}

/** Run the reaper if its interval has elapsed. Returns the next due timestamp. */
async function maybeReap(
  db: SupabaseClient,
  config: ScpConfig,
  dueAt: number,
): Promise<number> {
  if (Date.now() < dueAt) return dueAt;
  try {
    const n = await reapStaleJobs(db, config.reapTimeoutMs / 1000);
    if (n > 0) console.log(`[delta-scp] reaped ${n} orphaned job(s)`);
  } catch (err) {
    console.error('[delta-scp] reaper error:', err);
  }
  return Date.now() + config.reapIntervalMs;
}

/** Run the loop forever. Drains the queue, then idles one poll interval. */
export async function runWorker(
  db: SupabaseClient = getSupabase(),
  config: ScpConfig = loadConfig(),
  signal?: AbortSignal,
): Promise<void> {
  console.log(
    `[delta-scp] worker started · poll=${config.pollIntervalMs}ms · ` +
      `reap=${config.reapIntervalMs}ms/timeout=${config.reapTimeoutMs}ms`,
  );
  let reapDueAt = Date.now() + config.reapIntervalMs;
  while (!signal?.aborted) {
    reapDueAt = await maybeReap(db, config, reapDueAt);
    let handled = false;
    try {
      handled = await tick(db, config);
    } catch (err) {
      console.error('[delta-scp] tick error:', err);
    }
    if (!handled) await sleep(config.pollIntervalMs);
  }
}

// Direct entry: `npm run worker`
if (import.meta.url === `file://${process.argv[1]}`) {
  runWorker().catch((err) => {
    console.error('[delta-scp] fatal:', err);
    process.exit(1);
  });
}
