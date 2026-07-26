// End-to-end live verification of the worker path: enqueue a job, drive the
// worker's tick() (claim -> compress -> complete -> auto-populate graph), and
// confirm both the job result AND the graph landed via the worker itself — not
// by calling persistGraph directly. Self-cleaning. Authored as a one-shot smoke.
//
// Run (local repo, graph auto-populate on):
//   SCP_ALLOW_LOCAL=true SCP_GRAPH_AUTOPOPULATE=true npx tsx scripts/verify_worker_e2e.ts <local-dir>

import path from 'node:path';
import { loadConfig } from '../src/config.js';
import { getSupabase } from '../src/supabase.js';
import { enqueueJob, getJob } from '../src/queue.js';
import { tick } from '../src/worker.js';

const db = getSupabase();
const config = loadConfig();

function check(label: string, ok: boolean, detail: string) {
  console.log(`${ok ? 'PASS' : 'FAIL'} · ${label} · ${detail}`);
  if (!ok) process.exitCode = 1;
}

async function nodeCount(repoUrl: string): Promise<number> {
  const r = await db.from('ast_nodes').select('*', { count: 'exact', head: true }).eq('repo_name', repoUrl);
  return r.count ?? 0;
}

async function main() {
  const repo = path.resolve(process.argv[2] ?? 'src'); // small local dir by default
  console.log(`[e2e] repo=${repo} · graphAutoPopulate=${config.graphAutoPopulate} · allowLocal=${config.allowLocal}`);

  // Clean any prior graph rows for this repo path so the count assertion is honest.
  await db.from('ast_nodes').delete().eq('repo_name', repo);

  const job = await enqueueJob(db, repo);
  console.log(`[e2e] enqueued job ${job.id}`);

  // Drive ticks until our job leaves the queue (bounded — don't spin forever).
  let current = job;
  for (let i = 0; i < 10 && (current.status === 'pending' || current.status === 'processing'); i++) {
    await tick(db, config);
    current = (await getJob(db, job.id)) ?? current;
  }

  check('job completed via worker', current.status === 'complete', `status=${current.status}`);
  const cs = current.compressed_state as { stats?: { files_included?: number } } | null;
  check('compressed_state persisted', !!cs?.stats, `files_included=${cs?.stats?.files_included ?? 'n/a'}`);

  // The graph must have been auto-populated by tick() (not by us).
  const nodes = await nodeCount(repo);
  check('graph auto-populated by worker', nodes > 0, `ast_nodes=${nodes}`);

  // Cleanup: remove the graph rows and the job row — leave the DB as found.
  await db.from('ast_nodes').delete().eq('repo_name', repo);
  await db.from('scp_jobs').delete().eq('id', job.id);
  const after = await nodeCount(repo);
  const jobGone = (await getJob(db, job.id)) === null;
  check('cleanup', after === 0 && jobGone, `nodes=${after} jobRemoved=${jobGone}`);

  console.log(process.exitCode ? '\nRESULT: FAILURES present' : '\nRESULT: all checks passed');
}

main().catch((err) => {
  console.error('verify_worker_e2e error:', err);
  process.exit(1);
});
