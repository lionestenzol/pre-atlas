import { runClosureScan } from '../governance/closure_daemon.js';
const repo = 'C:/Users/bruke/Pre Atlas';
const r = await runClosureScan(repo);
console.log(JSON.stringify({
  scanned_at: r.scanned_at_iso,
  worktree_count: r.worktree_count,
  threshold_days: r.idle_threshold_days,
  candidates: r.candidates.length,
  active: r.active.length,
  report: r.report_path,
  top_candidates: r.candidates.slice(0, 5).map(c => ({ branch: c.branch, idle_days: c.idle_days, unique_commits: c.unique_commits })),
}, null, 2));
