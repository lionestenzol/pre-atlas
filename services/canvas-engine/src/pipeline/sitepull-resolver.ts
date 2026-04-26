import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { anatomyV1Schema, type AnatomyV1 } from '../adapter/v1-schema.js';

export interface ResolveResult {
  capturePath: string;
  envelope: AnatomyV1;
}

export interface SitepullResolverOptions {
  webAuditRoot: string;
}

export class SitepullResolver {
  private readonly roots: ReadonlyArray<string>;

  public constructor(opts: SitepullResolverOptions) {
    const base = path.resolve(opts.webAuditRoot);
    this.roots = [
      path.join(base, '.canvas'),
      path.join(base, '.tmp'),
      path.join(base, 'audits'),
    ];
  }

  public async resolve(url: string): Promise<ResolveResult | null> {
    const host = extractHost(url);
    if (host === null) {
      return null;
    }

    const candidates = await this.gatherCandidates(host);
    if (candidates.length === 0) {
      return null;
    }

    candidates.sort((left, right) => right.mtimeMs - left.mtimeMs);

    for (const candidate of candidates) {
      try {
        const raw = JSON.parse(await readFile(candidate.path, 'utf8')) as unknown;
        const envelope = anatomyV1Schema.parse(raw);
        return { capturePath: candidate.path, envelope };
      } catch {
        continue;
      }
    }

    return null;
  }

  private async gatherCandidates(
    host: string,
  ): Promise<Array<{ path: string; mtimeMs: number }>> {
    const results: Array<{ path: string; mtimeMs: number }> = [];

    for (const root of this.roots) {
      const matches = await this.findInRoot(root, host);
      results.push(...matches);
    }

    return results;
  }

  private async findInRoot(
    root: string,
    host: string,
  ): Promise<Array<{ path: string; mtimeMs: number }>> {
    const results: Array<{ path: string; mtimeMs: number }> = [];

    let entries: string[];
    try {
      entries = await readdir(root);
    } catch {
      return results;
    }

    // Walk every direct anatomy.json AND every <entry>/<child>/anatomy.json.
    // Stop using directory-name substring matching as the primary key —
    // arbitrarily-named .tmp captures (e.g. `hn-v1`, `example-v1`) were
    // skipped, and substring matches like "notexample.com" leaked into
    // requests for "example.com". Filename-based filtering is replaced with
    // metadata-based filtering: we read each anatomy.json and compare its
    // metadata.target hostname to the requested host (with optional
    // www. canonicalization both ways).
    const candidates: string[] = [];
    for (const entry of entries) {
      const entryPath = path.join(root, entry);
      const direct = path.join(entryPath, 'anatomy.json');
      if ((await safeStat(direct)) !== null) {
        candidates.push(direct);
        continue;
      }
      let nested: string[];
      try {
        nested = await readdir(entryPath);
      } catch {
        continue;
      }
      for (const child of nested) {
        const childPath = path.join(entryPath, child, 'anatomy.json');
        if ((await safeStat(childPath)) !== null) {
          candidates.push(childPath);
        }
      }
    }

    const wantedHost = canonicalizeHost(host);
    for (const candidatePath of candidates) {
      const candidateHost = await readAnatomyHost(candidatePath);
      if (candidateHost === null) continue;
      if (canonicalizeHost(candidateHost) !== wantedHost) continue;
      const st = await safeStat(candidatePath);
      if (st !== null) {
        results.push({ path: candidatePath, mtimeMs: st.mtimeMs });
      }
    }

    return results;
  }
}

function canonicalizeHost(host: string): string {
  const lowered = host.toLowerCase().trim();
  return lowered.startsWith('www.') ? lowered.slice(4) : lowered;
}

async function readAnatomyHost(p: string): Promise<string | null> {
  try {
    const raw = JSON.parse(await readFile(p, 'utf8')) as { metadata?: { target?: string } };
    const target = raw?.metadata?.target;
    if (typeof target !== 'string' || target.length === 0) return null;
    try {
      return new URL(target).hostname;
    } catch {
      return null;
    }
  } catch {
    return null;
  }
}

function extractHost(url: string): string | null {
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

async function safeStat(p: string): Promise<{ mtimeMs: number } | null> {
  try {
    const s = await stat(p);
    return s.isFile() ? { mtimeMs: s.mtimeMs } : null;
  } catch {
    return null;
  }
}
