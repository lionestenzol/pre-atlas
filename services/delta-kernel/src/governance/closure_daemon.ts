/**
 * Bookmark scan -- refresh the central worktree bookmark index.
 *
 * Doctrine (Bruke, 2026-07-25): worktrees are project bookmarks answering
 * three questions on sight -- what was I reaching for, what's left, did I
 * finish? Central index lives at capsules/BOOKMARKS.md, written by
 * scripts/scan_worktree_bookmarks.py. Done = merged to main OR capsule/*
 * tagged. Nothing is closed. Nothing is deleted. Read-only per
 * TRUST_BOUNDARY.md.
 *
 * Previous shape ("candidates for closure" with suggested delete commands)
 * was superseded 2026-07-25 -- see memory: project_worktree_bookmarks.md.
 * The runClosureScan export name is preserved so the governance daemon
 * caller doesn't need renaming, but its behavior is now "run the bookmark
 * refresher and report summary."
 */
import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export interface BookmarkScanSummary {
  generated_at: string;
  index_path: string;
  total: number;
  open: number;
  merged: number;
  tagged: number;
}

export interface ClosureScanResult {
  scanned_at_iso: string;
  worktree_count: number;
  report_path: string;
  open_count: number;
  merged_count: number;
  tagged_count: number;
  /** @deprecated Kept only for backward compatibility with the daemon caller. Always empty. */
  candidates: never[];
}

export interface RunClosureScanOptions {
  pythonBin?: string;
  scriptPath?: string;
  clock?: () => Date;
}

function resolvePython(preferred?: string): string {
  if (preferred) return preferred;
  return process.env.PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');
}

export async function runClosureScan(
  repoRoot: string,
  opts: RunClosureScanOptions = {},
): Promise<ClosureScanResult> {
  const clock = opts.clock ?? (() => new Date());
  const script = opts.scriptPath ?? path.join(repoRoot, 'scripts', 'scan_worktree_bookmarks.py');
  const python = resolvePython(opts.pythonBin);

  if (!fs.existsSync(script)) {
    throw new Error(`Bookmark scan script missing at ${script}`);
  }

  execFileSync(python, [script], {
    cwd: repoRoot,
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'pipe'],
    maxBuffer: 8 * 1024 * 1024,
  });

  const summaryPath = path.join(repoRoot, 'capsules', 'BOOKMARKS.json');
  if (!fs.existsSync(summaryPath)) {
    throw new Error(`Bookmark scan produced no summary at ${summaryPath}`);
  }
  const summary: BookmarkScanSummary = JSON.parse(
    fs.readFileSync(summaryPath, { encoding: 'utf-8' }),
  );

  return {
    scanned_at_iso: clock().toISOString(),
    worktree_count: summary.total,
    report_path: summary.index_path,
    open_count: summary.open,
    merged_count: summary.merged,
    tagged_count: summary.tagged,
    candidates: [],
  };
}
