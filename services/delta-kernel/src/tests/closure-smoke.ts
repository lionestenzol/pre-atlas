import { runClosureScan } from '../governance/closure_daemon.js';
const repo = 'C:/Users/bruke/Pre Atlas';
const r = await runClosureScan(repo);
console.log(JSON.stringify({
  scanned_at: r.scanned_at_iso,
  worktree_count: r.worktree_count,
  open: r.open_count,
  merged: r.merged_count,
  tagged: r.tagged_count,
  report: r.report_path,
}, null, 2));
