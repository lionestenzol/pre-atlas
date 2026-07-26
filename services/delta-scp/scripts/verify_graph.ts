// One-shot live verification of the AST graph sync against Supabase.
// Throwaway repo_name; cleans up after itself. Run: npx tsx scripts/verify_graph.ts
//
// Proves the load-bearing claims that unit tests + types could not:
//   1. persistGraph writes nodes + cross-file `imports` edges to the live DB
//   2. it is idempotent (a re-run yields identical counts)
//   3. delete-and-replace removes stale rows (drop a file -> its rows vanish)
//   4. readFocusFromGraph returns a focus file + its one-hop import neighbours

import { getSupabase } from '../src/supabase.js';
import { buildGraphRows, persistGraph, readFocusFromGraph } from '../src/graph.js';
import type { SourceFile } from '../src/compressor.js';

const REPO = 'verify://selftest-graph';
const db = getSupabase();

const FULL: SourceFile[] = [
  { path: 'a.ts', content: "import { b } from './b';\nexport function a() {}\n" },
  { path: 'b.ts', content: 'export function b() {}\n' },
  { path: 'c.ts', content: 'export function c() {}\n' },
];
const DROPPED = FULL.filter((f) => f.path !== 'c.ts'); // c.ts removed

async function counts() {
  const n = await db.from('ast_nodes').select('*', { count: 'exact', head: true }).eq('repo_name', REPO);
  const ids = await db.from('ast_nodes').select('id').eq('repo_name', REPO);
  const idList = (ids.data ?? []).map((r: { id: string }) => r.id);
  let edgeCount = 0;
  if (idList.length) {
    const e = await db
      .from('ast_edges')
      .select('*', { count: 'exact', head: true })
      .or(`source_id.in.(${idList.join(',')}),target_id.in.(${idList.join(',')})`);
    edgeCount = e.count ?? 0;
  }
  return { nodes: n.count ?? 0, edges: edgeCount };
}

function check(label: string, ok: boolean, detail: string) {
  console.log(`${ok ? 'PASS' : 'FAIL'} · ${label} · ${detail}`);
  if (!ok) process.exitCode = 1;
}

async function main() {
  // clean slate
  await db.from('ast_nodes').delete().eq('repo_name', REPO);

  // 1. write
  const r1 = await persistGraph(db, REPO, buildGraphRows(REPO, FULL));
  const c1 = await counts();
  check('write nodes', c1.nodes === 6, `db nodes=${c1.nodes} (expect 6) · persist reported ${r1.nodes}`);
  check('write cross-file edge', c1.edges === 1, `db edges=${c1.edges} (expect 1: a.ts->b.ts) · persist reported ${r1.edges}`);

  // 2. idempotency
  await persistGraph(db, REPO, buildGraphRows(REPO, FULL));
  const c2 = await counts();
  check('idempotent re-run', c2.nodes === 6 && c2.edges === 1, `nodes=${c2.nodes} edges=${c2.edges} (expect 6/1)`);

  // 3. stale removal: drop c.ts
  await persistGraph(db, REPO, buildGraphRows(REPO, DROPPED));
  const c3 = await counts();
  check('stale rows removed', c3.nodes === 4 && c3.edges === 1, `nodes=${c3.nodes} edges=${c3.edges} (expect 4/1 after dropping c.ts)`);

  // 4. focus closure
  const focus = await readFocusFromGraph(db, REPO, ['a.ts']);
  const f = new Set(focus);
  check('focus closure (a.ts + import neighbour b.ts)', f.has('a.ts') && f.has('b.ts'), `focus=[${[...f].sort().join(', ')}]`);

  // cleanup — leave the DB as we found it
  const del = await db.from('ast_nodes').delete().eq('repo_name', REPO);
  const after = await counts();
  check('cleanup', after.nodes === 0, `nodes after cleanup=${after.nodes}${del.error ? ' · delete error: ' + del.error.message : ''}`);

  console.log(process.exitCode ? '\nRESULT: FAILURES present' : '\nRESULT: all checks passed');
}

main().catch((err) => {
  console.error('verify_graph error:', err);
  process.exit(1);
});
