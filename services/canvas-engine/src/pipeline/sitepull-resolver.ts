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

    for (const entry of entries) {
      if (!entry.toLowerCase().includes(host.toLowerCase())) {
        continue;
      }

      const entryPath = path.join(root, entry);
      const direct = path.join(entryPath, 'anatomy.json');
      const directStat = await safeStat(direct);
      if (directStat !== null) {
        results.push({ path: direct, mtimeMs: directStat.mtimeMs });
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
        const childStat = await safeStat(childPath);
        if (childStat !== null) {
          results.push({ path: childPath, mtimeMs: childStat.mtimeMs });
        }
      }
    }

    return results;
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
