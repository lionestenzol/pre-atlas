// Delta SCP · repository source loader (clone or local path -> SourceFile[])

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, readdir, rm, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { compressTreeAsync, type CompressedState, type SourceFile } from './compressor.js';
import { loadConfig, type ScpConfig } from './config.js';
import { validateRepoUrl } from './validate.js';

const execFileAsync = promisify(execFile);

// Directories that never carry useful symbols — skipped wholesale.
const IGNORE_DIRS = new Set([
  '.git',
  'node_modules',
  'dist',
  'build',
  'out',
  '.next',
  '.nuxt',
  '.cache',
  'coverage',
  'vendor',
  '__pycache__',
  '.venv',
  'venv',
  '.tox',
  'target',
  '.idea',
  '.vscode',
]);

// Extensions worth scanning for structure. Everything else (images, binaries,
// lockfiles, archives) is skipped.
const INCLUDE_EXT = new Set([
  'ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs',
  'py', 'go', 'rs', 'java', 'rb', 'php',
  'c', 'h', 'cpp', 'hpp', 'cs', 'swift', 'kt',
  'sql', 'sh', 'html', 'md', 'json', 'yaml', 'yml', 'toml',
]);

function includeFile(name: string): boolean {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return INCLUDE_EXT.has(ext);
}

// A file present in the repo but not analyzed, and why. Surfaced in the dossier
// so a coverage hole is NAMED, never silently hidden. An unnamed skip (the old
// behaviour) let the report imply full coverage it didn't have.
// See ~/.claude/rules/common/code-as-furniture.md — fail loud, don't degrade silently.
export interface SkippedFile {
  path: string;
  ext: string;
  reason: 'unsupported-ext' | 'too-large';
}

export interface WalkResult {
  files: SourceFile[];
  skipped: SkippedFile[];
}

// Mirrors validate.ts' notion of a local path so a repo_url accepted as "local"
// is also fetched as local (absolute or resolvable relative path that exists).
function isLocalPath(repoUrl: string): boolean {
  if (repoUrl.startsWith('file://')) return true;
  if (path.isAbsolute(repoUrl)) return existsSync(repoUrl);
  return existsSync(path.resolve(repoUrl));
}

function localDir(repoUrl: string): string {
  return repoUrl.startsWith('file://')
    ? repoUrl.slice('file://'.length)
    : path.resolve(repoUrl);
}

/**
 * Recursively collect includable source files under root, honouring ignores.
 * Aborts (throws) if the repo blows past the file-count or total-byte caps —
 * a guardrail against a hostile or accidentally enormous repo.
 */
async function walk(root: string, config: ScpConfig): Promise<WalkResult> {
  const files: SourceFile[] = [];
  const skipped: SkippedFile[] = [];
  let totalBytes = 0;

  async function recurse(dir: string): Promise<void> {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (IGNORE_DIRS.has(entry.name)) continue;
        await recurse(abs);
      } else if (entry.isFile()) {
        const rel = path.relative(root, abs).split(path.sep).join('/');
        const ext = entry.name.split('.').pop()?.toLowerCase() ?? '';
        if (!includeFile(entry.name)) {
          // Record instead of silently dropping — an unnamed coverage hole is
          // the worst kind. Aggregated by extension in the dossier.
          skipped.push({ path: rel, ext, reason: 'unsupported-ext' });
          continue;
        }
        const info = await stat(abs);
        if (info.size > config.maxFileBytes) {
          skipped.push({ path: rel, ext, reason: 'too-large' });
          continue;
        }
        if (files.length >= config.maxFiles) {
          throw new Error(`repo exceeds maxFiles (${config.maxFiles})`);
        }
        totalBytes += info.size;
        if (totalBytes > config.maxTotalBytes) {
          throw new Error(`repo exceeds maxTotalBytes (${config.maxTotalBytes})`);
        }
        const content = await readFile(abs, 'utf8');
        files.push({ path: rel, content });
      }
    }
  }

  await recurse(root);
  return { files, skipped };
}

function clonePrefix(cloneDir: string, repoUrl: string): string {
  const slug = createHash('sha256').update(repoUrl).digest('hex').slice(0, 16);
  return path.join(cloneDir, `${slug}-`);
}

/**
 * Shallow-clone a remote repo into a unique per-run directory. Using mkdtemp
 * (rather than a deterministic per-URL path that gets rm'd) means two workers
 * processing the same repo_url never delete each other's checkout mid-run.
 */
async function cloneRepo(repoUrl: string, config: ScpConfig): Promise<string> {
  // Resolve to an absolute, drive-qualified path. A drive-relative path such as
  // `\tmp\delta-scp\…` (what a `/tmp/...` cloneDir yields on Windows) trips a
  // Git-for-Windows bug: cloning into a *pre-existing empty* directory via such
  // a path wrongly fails with "already exists and is not an empty directory".
  // mkdtemp pre-creates the dir for race-safety, so we always hit that path;
  // path.resolve hands git an absolute `C:\…` path it checks correctly.
  // See ~/.claude/rules/common/code-as-furniture.md — fixed, not documented.
  const baseDir = path.resolve(config.cloneDir);
  await mkdir(baseDir, { recursive: true });
  const target = await mkdtemp(clonePrefix(baseDir, repoUrl));
  // The `--` end-of-options marker is load-bearing: repoUrl is the job queue's
  // external input (POST /jobs {repo_url}), and validateRepoUrl's scp-like
  // parser (user@host:path) only checks the extracted host, not that the full
  // string doesn't start with `-`. Without `--`, a crafted repoUrl such as
  // `-oProxyCommand=... @host:path` is parsed by `git clone` as an OPTION, not
  // a positional URL (verified: `git clone -x` -> "unknown switch 'x'" without
  // `--`, vs. correctly literal `repository '-x' does not exist` with `--`) —
  // the classic CVE-2017-1000117-shaped git argument-injection class. `--`
  // forces every remaining argument (repoUrl AND target) to be positional
  // regardless of leading dashes, closing it independent of the URL's shape.
  await execFileAsync(
    'git',
    ['clone', '--depth', '1', '--quiet', '--', repoUrl, target],
    {
      timeout: 120_000,
      maxBuffer: 16 * 1024 * 1024,
      // Never block on a credential prompt; never let a URL invoke ext helpers.
      env: { ...process.env, GIT_TERMINAL_PROMPT: '0' },
    },
  );
  return target;
}

/**
 * Fetch a repo's source files (local path or git clone), honouring the walk
 * guardrails, and clean up any clone it created. Content is fully read into
 * memory during the walk, so the checkout can be removed before returning.
 *
 * Extracted so consumers that need the raw files — e.g. the worker populating
 * the AST graph — can reuse a single fetch instead of cloning twice.
 */
export async function fetchSourceFilesDetailed(
  repoUrl: string,
  config: ScpConfig = loadConfig(),
): Promise<WalkResult> {
  // Defense in depth: the API gateway validates too, but the worker may be fed
  // jobs from other producers, so re-check before touching the network/disk.
  const verdict = validateRepoUrl(repoUrl, config);
  if (!verdict.ok) {
    throw new Error(`rejected repo_url: ${verdict.reason}`);
  }

  let root: string;
  let cleanup = false;

  if (isLocalPath(repoUrl)) {
    root = localDir(repoUrl);
  } else {
    root = await cloneRepo(repoUrl, config);
    cleanup = true;
  }

  try {
    return await walk(root, config);
  } finally {
    if (cleanup) {
      await rm(root, { recursive: true, force: true }).catch(() => {});
    }
  }
}

/**
 * Back-compat convenience: the analyzable files only (drops the skip list).
 * Callers that need the coverage tally use fetchSourceFilesDetailed.
 */
export async function fetchSourceFiles(
  repoUrl: string,
  config: ScpConfig = loadConfig(),
): Promise<SourceFile[]> {
  return (await fetchSourceFilesDetailed(repoUrl, config)).files;
}

/**
 * Full pipeline step 3: fetch the repo and compress it into the symbolic map.
 */
export async function compressRepository(
  repoUrl: string,
  config: ScpConfig = loadConfig(),
): Promise<CompressedState> {
  const files = await fetchSourceFiles(repoUrl, config);
  return compressTreeAsync(repoUrl, files, new Date().toISOString(), config.extractor);
}
