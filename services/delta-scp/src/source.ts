// Delta SCP · repository source loader (clone or local path -> SourceFile[])

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { existsSync } from 'node:fs';
import { mkdir, readFile, readdir, rm, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { compressTree, type CompressedState, type SourceFile } from './compressor.js';
import { loadConfig, type ScpConfig } from './config.js';

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

function isLocalPath(repoUrl: string): boolean {
  if (repoUrl.startsWith('file://')) return true;
  if (path.isAbsolute(repoUrl) && existsSync(repoUrl)) return true;
  return false;
}

function localDir(repoUrl: string): string {
  return repoUrl.startsWith('file://') ? repoUrl.slice('file://'.length) : repoUrl;
}

/** Recursively collect includable source files under root, honouring ignores. */
async function walk(root: string, maxFileBytes: number): Promise<SourceFile[]> {
  const files: SourceFile[] = [];

  async function recurse(dir: string): Promise<void> {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (IGNORE_DIRS.has(entry.name)) continue;
        await recurse(abs);
      } else if (entry.isFile() && includeFile(entry.name)) {
        const info = await stat(abs);
        if (info.size > maxFileBytes) continue;
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

function cloneTarget(cloneDir: string, repoUrl: string): string {
  const slug = createHash('sha1').update(repoUrl).digest('hex').slice(0, 16);
  return path.join(cloneDir, slug);
}

/** Shallow-clone a remote repo into the clone dir (fresh each time). */
async function cloneRepo(repoUrl: string, config: ScpConfig): Promise<string> {
  await mkdir(config.cloneDir, { recursive: true });
  const target = cloneTarget(config.cloneDir, repoUrl);
  await rm(target, { recursive: true, force: true });
  await execFileAsync(
    'git',
    ['clone', '--depth', '1', '--quiet', repoUrl, target],
    { timeout: 120_000, maxBuffer: 16 * 1024 * 1024 },
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
  let root: string;
  let cleanup = false;

  if (isLocalPath(repoUrl)) {
    root = localDir(repoUrl);
  } else {
    root = await cloneRepo(repoUrl, config);
    cleanup = true;
  }

  try {
    const files = await walk(root, config.maxFileBytes);
    return compressTree(repoUrl, files);
  } finally {
    if (cleanup) {
      await rm(root, { recursive: true, force: true }).catch(() => {});
    }
  }
}
