import { describe, it, expect } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  computeFnStats, buildHotspots, buildIdentity, collectRiskySurfaces, renderReport,
  modernizeRepo, DOSSIER_VERSION,
} from './modernize.js';
import { buildGraphRowsAst } from './graph.js';
import { compressTreeAsync, type SourceFile } from './compressor.js';
import type { ScpConfig } from './config.js';

// A C repo: helper is called by two functions (fan-in 2); run calls strcpy (risk).
const FILES: SourceFile[] = [
  {
    path: 'src/util.c',
    content: `int helper(int x) { return x + 1; }
int twice(int x) { return helper(helper(x)); }
`,
  },
  {
    path: 'src/main.c',
    content: `#include <string.h>
int helper(int x);
void run(char* dst, char* src) {
  strcpy(dst, src);
  int r = helper(2);
}
`,
  },
];

const cfg = (extractor: 'regex' | 'treesitter'): ScpConfig => ({
  supabaseUrl: '', supabaseServiceKey: '', port: 3012, pollIntervalMs: 5000,
  cloneDir: os.tmpdir(), maxFileBytes: 1 << 20, reapTimeoutMs: 1000, reapIntervalMs: 1000,
  apiKey: '', allowedHosts: [], allowLocal: true, maxFiles: 1000, maxTotalBytes: 1 << 20,
  flueDir: os.tmpdir(), graphAutoPopulate: false, extractor,
});

describe('modernize dossier · builders', () => {
  it('computes fan-in / fan-out from the AST call graph', async () => {
    const graph = await buildGraphRowsAst('repo', FILES);
    const stats = computeFnStats(graph);
    // helper defined in util.c; called by twice (x2 in one expr dedups to 1 edge) — fan-in >= 1
    const helper = [...stats.values()].find((f) => f.name === 'helper' && f.file === 'src/util.c');
    expect(helper).toBeTruthy();
    expect(helper!.fan_in).toBeGreaterThanOrEqual(1);
    const twice = [...stats.values()].find((f) => f.name === 'twice');
    expect(twice!.fan_out).toBeGreaterThanOrEqual(1);
  });

  it('ranks hotspots: helper is a core utility', async () => {
    const graph = await buildGraphRowsAst('repo', FILES);
    const compressed = await compressTreeAsync('repo', FILES, 'T', 'treesitter');
    const hot = buildHotspots(compressed, computeFnStats(graph));
    expect(hot.core_utilities[0]?.name).toBe('helper');
    expect(hot.god_files.length).toBeGreaterThan(0);
  });

  it('detects risky call surfaces (strcpy) via raw call pairs', async () => {
    const risky = await collectRiskySurfaces(FILES, 'treesitter');
    const strcpy = risky.find((r) => r.target === 'strcpy');
    expect(strcpy).toBeTruthy();
    expect(strcpy!.caller).toBe('run');
    expect(strcpy!.file).toBe('src/main.c');
  });

  it('regex extractor finds no risky surfaces (no call graph)', async () => {
    expect(await collectRiskySurfaces(FILES, 'regex')).toEqual([]);
  });

  // Mirrors the real bug the proof-run found (2026-07-13, URBANNOMAD): a call-only
  // risk scan reported "0 risky surfaces" on code with real innerHTML-assignment
  // XSS and member-called sinks (document.write), because both shapes were
  // structurally invisible to a bare-identifier call query.
  it('finds JS assignment-form DOM sinks AND member-style calls (both were invisible before)', async () => {
    const jsFiles: SourceFile[] = [{
      path: 'src/ui.js',
      content: `function updateZoneLogsUI(container, log) {
  container.innerHTML = '';
  document.write(log.raw);
  const link = document.createElement('a');
  link.href = log.url;
}`,
    }];
    const risky = await collectRiskySurfaces(jsFiles, 'treesitter');

    const assign = risky.find((r) => r.kind === 'assignment' && r.target === 'innerHTML');
    expect(assign).toBeTruthy();
    expect(assign!.caller).toBe('updateZoneLogsUI');

    // qualified name, not the generic 'write' — bare property names are too
    // common (fs.write, res.write) to safely denylist on their own
    const call = risky.find((r) => r.kind === 'call' && r.target === 'document.write');
    expect(call).toBeTruthy();
    expect(call!.caller).toBe('updateZoneLogsUI');
    expect(risky.some((r) => r.target === 'write')).toBe(false);

    // precision: `.href = ` is NOT in the DOM-sink denylist — must not false-positive
    expect(risky.some((r) => r.target === 'href')).toBe(false);

    const graph = await buildGraphRowsAst('repo', jsFiles);
    const compressed = await compressTreeAsync('repo', jsFiles, 'T', 'treesitter');
    const ident = buildIdentity(compressed);
    const hot = buildHotspots(compressed, computeFnStats(graph));
    const md = renderReport('repo', ident, graph, hot, risky, 'treesitter');
    expect(md).toContain('.innerHTML` assigned in `updateZoneLogsUI`');
    expect(md).toContain('`document.write` called by `updateZoneLogsUI`');
  });

  it('identity flags legacy languages present', async () => {
    const compressed = await compressTreeAsync('repo', FILES, 'T', 'treesitter');
    const ident = buildIdentity(compressed);
    expect(ident.legacy_languages).toContain('c');
    expect(ident.total_symbols).toBeGreaterThan(0);
  });

  it('report renders every section', async () => {
    const graph = await buildGraphRowsAst('repo', FILES);
    const compressed = await compressTreeAsync('repo', FILES, 'T', 'treesitter');
    const ident = buildIdentity(compressed);
    const hot = buildHotspots(compressed, computeFnStats(graph));
    const risky = await collectRiskySurfaces(FILES, 'treesitter');
    const md = renderReport('repo', ident, graph, hot, risky, 'treesitter');
    for (const h of ['## 1.', '## 2.', '## 3.', '## 4.', '## 5.']) expect(md).toContain(h);
    expect(md).toContain('strcpy');
  });
});

describe('modernize dossier · end-to-end', () => {
  it('writes all three artifacts and a content-addressed receipt', async () => {
    const repo = await fs.mkdtemp(path.join(os.tmpdir(), 'scp-mod-'));
    const out = await fs.mkdtemp(path.join(os.tmpdir(), 'scp-out-'));
    try {
      await fs.mkdir(path.join(repo, 'src'), { recursive: true });
      await fs.writeFile(path.join(repo, 'src', 'a.c'), FILES[0].content);
      await fs.writeFile(path.join(repo, 'src', 'b.c'), FILES[1].content);

      const receipt = await modernizeRepo(repo, out, cfg('treesitter'));
      expect(receipt.status).toBe('ok');
      expect(receipt.dossier_version).toBe(DOSSIER_VERSION);
      expect(receipt.sha256).toMatch(/^[0-9a-f]{64}$/);
      expect(receipt.data.risky_surfaces).toBeGreaterThanOrEqual(1);

      for (const f of ['symbolic_map.json', 'dependency_graph.json', 'MODERNIZATION_REPORT.md']) {
        await expect(fs.stat(path.join(out, f))).resolves.toBeTruthy();
      }
      // deterministic content-address: a second run over the same tree matches.
      const out2 = await fs.mkdtemp(path.join(os.tmpdir(), 'scp-out2-'));
      const receipt2 = await modernizeRepo(repo, out2, cfg('treesitter'));
      expect(receipt2.sha256).toBe(receipt.sha256);
      await fs.rm(out2, { recursive: true, force: true });
    } finally {
      await fs.rm(repo, { recursive: true, force: true });
      await fs.rm(out, { recursive: true, force: true });
    }
  });
});
