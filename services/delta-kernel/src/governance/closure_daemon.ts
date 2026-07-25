/**
 * Closure Daemon -- surface branches ripe for closure without touching them.
 *
 * The fan-out-then-abandon signature: 31 worktree branches most frozen at
 * 60-100 commits the moment their theme cooled. Closure = resolved-with-a-
 * record (minidocs template), not merged-to-main. This runner enumerates
 * worktrees, ranks them by idle time + unique-work volume, and emits a
 * dated scan report to capsules/ for human review. It never merges, tags,
 * or deletes -- destructive branch actions stay human-gated per
 * TRUST_BOUNDARY.md.
 */
import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export interface WorktreeInfo {
  path: string;
  branch: string;
  head: string;
  head_subject: string;
  head_date_iso: string;
  idle_days: number;
  unique_commits: number;
  is_main_worktree: boolean;
}

export interface ClosureScanResult {
  scanned_at_iso: string;
  worktree_count: number;
  idle_threshold_days: number;
  candidates: WorktreeInfo[];
  active: WorktreeInfo[];
  report_path: string;
}

function runGit(repoRoot: string, args: string[]): string {
  return execFileSync('git', args, {
    cwd: repoRoot,
    encoding: 'utf-8',
    maxBuffer: 32 * 1024 * 1024,
  }).trim();
}

function tryGit(repoRoot: string, args: string[]): string | null {
  try {
    return runGit(repoRoot, args);
  } catch {
    return null;
  }
}

function parseWorktreeList(porcelain: string, repoRoot: string): Array<{ path: string; branch: string; head: string; is_main: boolean }> {
  const entries: Array<{ path: string; branch: string; head: string; is_main: boolean }> = [];
  let current: { path?: string; branch?: string; head?: string } = {};
  for (const line of porcelain.split(/\r?\n/)) {
    if (line.startsWith('worktree ')) {
      if (current.path) {
        entries.push({
          path: current.path,
          branch: current.branch ?? '(detached)',
          head: current.head ?? '',
          is_main: path.resolve(current.path) === path.resolve(repoRoot),
        });
      }
      current = { path: line.slice('worktree '.length) };
    } else if (line.startsWith('HEAD ')) {
      current.head = line.slice('HEAD '.length);
    } else if (line.startsWith('branch ')) {
      current.branch = line.slice('branch '.length).replace(/^refs\/heads\//, '');
    } else if (line === 'detached') {
      current.branch = '(detached)';
    }
  }
  if (current.path) {
    entries.push({
      path: current.path,
      branch: current.branch ?? '(detached)',
      head: current.head ?? '',
      is_main: path.resolve(current.path) === path.resolve(repoRoot),
    });
  }
  return entries;
}

function resolveMainlineRef(repoRoot: string): string {
  const candidates = ['origin/main', 'origin/master', 'main', 'master'];
  for (const ref of candidates) {
    if (tryGit(repoRoot, ['rev-parse', '--verify', ref]) !== null) {
      return ref;
    }
  }
  return 'HEAD';
}

function daysBetween(nowMs: number, thenIso: string): number {
  const then = Date.parse(thenIso);
  if (Number.isNaN(then)) return 0;
  return Math.floor((nowMs - then) / (1000 * 60 * 60 * 24));
}

function collectWorktreeInfo(repoRoot: string, mainRef: string): WorktreeInfo[] {
  const porcelain = runGit(repoRoot, ['worktree', 'list', '--porcelain']);
  const raw = parseWorktreeList(porcelain, repoRoot);
  const nowMs = Date.now();
  const out: WorktreeInfo[] = [];
  for (const wt of raw) {
    if (!wt.head) continue;
    const subject = tryGit(repoRoot, ['log', '-1', '--format=%s', wt.head]) ?? '';
    const dateIso = tryGit(repoRoot, ['log', '-1', '--format=%cI', wt.head]) ?? '';
    const uniqueRaw = wt.is_main
      ? null
      : tryGit(repoRoot, ['rev-list', '--count', `${mainRef}..${wt.head}`]);
    out.push({
      path: wt.path,
      branch: wt.branch,
      head: wt.head,
      head_subject: subject,
      head_date_iso: dateIso,
      idle_days: dateIso ? daysBetween(nowMs, dateIso) : 0,
      unique_commits: uniqueRaw ? parseInt(uniqueRaw, 10) : 0,
      is_main_worktree: wt.is_main,
    });
  }
  return out;
}

function renderReport(result: ClosureScanResult, mainRef: string): string {
  const lines: string[] = [];
  lines.push(`# Closure scan -- ${result.scanned_at_iso.slice(0, 10)}`);
  lines.push('');
  lines.push(`Scanned ${result.worktree_count} worktrees against \`${mainRef}\`. Idle threshold: **${result.idle_threshold_days} days**.`);
  lines.push('');
  lines.push('This is a read-only surfacing pass. Nothing was merged, tagged, or deleted. Review candidates and take action manually.');
  lines.push('');
  lines.push(`## Candidates for closure (${result.candidates.length})`);
  lines.push('');
  if (result.candidates.length === 0) {
    lines.push('_No idle branches above threshold._');
  } else {
    lines.push('| branch | idle | unique commits | HEAD | subject |');
    lines.push('|---|---:|---:|---|---|');
    for (const c of result.candidates) {
      const subj = c.head_subject.replace(/\|/g, '\\|').slice(0, 80);
      lines.push(`| \`${c.branch}\` | ${c.idle_days}d | ${c.unique_commits} | \`${c.head.slice(0, 8)}\` | ${subj} |`);
    }
    lines.push('');
    lines.push('### Suggested actions per capsule');
    lines.push('');
    for (const c of result.candidates) {
      lines.push(`- **${c.branch}** -- \`git log ${mainRef}..${c.branch}\` to review · \`git tag -a capsule/${c.branch.replace(/[^a-zA-Z0-9._-]/g, '-')}-${result.scanned_at_iso.slice(0, 10)} ${c.head} -m "what I was reaching for"\` to freeze · then \`git worktree remove <path>\` + \`git branch -D ${c.branch}\` to close.`);
    }
  }
  lines.push('');
  lines.push(`## Active worktrees (${result.active.length})`);
  lines.push('');
  if (result.active.length === 0) {
    lines.push('_None._');
  } else {
    lines.push('| branch | idle | unique commits | subject |');
    lines.push('|---|---:|---:|---|');
    for (const a of result.active) {
      const subj = a.head_subject.replace(/\|/g, '\\|').slice(0, 80);
      const branchTag = a.is_main_worktree ? `\`${a.branch}\` (main)` : `\`${a.branch}\``;
      lines.push(`| ${branchTag} | ${a.idle_days}d | ${a.unique_commits} | ${subj} |`);
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('_Generated by `governance_daemon.closure_scan`. Read-only per TRUST_BOUNDARY.md -- destructive branch actions are human-gated._');
  return lines.join('\n');
}

export interface RunClosureScanOptions {
  idleThresholdDays?: number;
  capsulesDir?: string;
  clock?: () => Date;
}

export async function runClosureScan(repoRoot: string, opts: RunClosureScanOptions = {}): Promise<ClosureScanResult> {
  const threshold = opts.idleThresholdDays ?? parseInt(process.env.CLOSURE_IDLE_DAYS ?? '14', 10);
  const capsulesDir = opts.capsulesDir ?? path.join(repoRoot, 'capsules');
  const clock = opts.clock ?? (() => new Date());

  const mainRef = resolveMainlineRef(repoRoot);
  const worktrees = collectWorktreeInfo(repoRoot, mainRef);

  const candidates = worktrees
    .filter((w) => !w.is_main_worktree && w.idle_days >= threshold)
    .sort((a, b) => b.idle_days - a.idle_days || b.unique_commits - a.unique_commits);
  const active = worktrees
    .filter((w) => w.is_main_worktree || w.idle_days < threshold)
    .sort((a, b) => a.idle_days - b.idle_days);

  const scannedAt = clock();
  const scannedIso = scannedAt.toISOString();
  const stamp = scannedIso.slice(0, 10);

  const result: ClosureScanResult = {
    scanned_at_iso: scannedIso,
    worktree_count: worktrees.length,
    idle_threshold_days: threshold,
    candidates,
    active,
    report_path: path.join(capsulesDir, `scan-${stamp}.md`),
  };

  if (!fs.existsSync(capsulesDir)) {
    fs.mkdirSync(capsulesDir, { recursive: true });
  }
  fs.writeFileSync(result.report_path, renderReport(result, mainRef), { encoding: 'utf-8' });

  return result;
}
