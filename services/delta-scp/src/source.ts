// Delta SCP · repository source loader (clone or local path -> SourceFile[])

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, readdir, rm, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { compressTree, type CompressedState, type SourceFile } from './compressor.js';
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
  'sql', 'sh', 'md', 'json', 'yaml', 'yml', 'toml',
]);

function includeFile(name: string): boolean {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return INCLUDE_EXT.has(ext);
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
async function walk(root: string, config: ScpConfig): Promise<SourceFile[]> {
  const files: SourceFile[] = [];
  let totalBytes = 0;

  async function recurse(dir: string): Promise<void> {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (IGNORE_DIRS.has(entry.name)) continue;
        await recurse(abs);
      } else if (entry.isFile() && includeFile(entry.name)) {
        const info = await stat(abs);
        if (info.size > config.maxFileBytes) continue;
        if (files.length >= config.maxFiles) {
          throw new Error(`repo exceeds maxFiles (${config.maxFiles})`);
        }
        totalBytes += info.size;
        if (totalBytes > config.maxTotalBytes) {
          throw new Error(`repo exceeds maxTotalBytes (${config.maxTotalBytes})`);
        }
        const content = await readFile(abs, 'utf8');
        files.push({
          path: path.relative(root, abs).split(path.sep).join('/'),
          content,
        });
      }
    }
  }

  await recurse(root);
  return files;
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
  await mkdir(config.cloneDir, { recursive: true });
  const target = await mkdtemp(clonePrefix(config.cloneDir, repoUrl));
  await execFileAsync(
    'git',
    ['clone', '--depth', '1', '--quiet', repoUrl, target],
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
 * Full pipeline step 3: fetch the repo (local path or git clone) and compress it
 * into the symbolic map. Cleans up any clone it created.
 */
export async function compressRepository(
  repoUrl: string,
  config: ScpConfig = loadConfig(),
): Promise<CompressedState> {
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
    const files = await walk(root, config);
    return compressTree(repoUrl, files, new Date().toISOString());
  } finally {
    if (cleanup) {
      await rm(root, { recursive: true, force: true }).catch(() => {});
    }
  }
}
