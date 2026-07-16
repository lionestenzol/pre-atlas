import { describe, it, expect } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  computeFnStats, buildHotspots, buildIdentity, collectRiskySurfaces, findDeadCodeCandidates,
  renderReport, modernizeRepo, DOSSIER_VERSION,
} from './modernize.js';
import { buildGraphRowsAst } from './graph.js';
import { compressTreeAsync, type SourceFile } from './compressor.js';
import { collectSecretFindings } from './secrets.js';
import type { ScpConfig } from './config.js';

// See secrets.test.ts for why this is joined rather than a literal.
const FAKE_STRIPE_KEY = ['sk', 'test', '4eC39HqLyjWDarjtT1zdp7dc'].join('_');

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

  // The exact bug found live 2026-07-14 running the dossier against a real repo
  // (delta-kernel): `this.db.exec(DDL)` (better-sqlite3's schema-exec method) got
  // misflagged as shell-exec/injection risk, because a bare 'exec'/'spawn' member
  // callee name can't tell RegExp.exec()/db.exec() apart from child_process.exec()
  // without checking the receiver.
  it('does NOT flag a receiver-ambiguous .exec()/.spawn() member call (this.db.exec, RegExp.exec) — no known-dangerous receiver, no flag', async () => {
    const jsFiles: SourceFile[] = [{
      path: 'src/store.js',
      content: `class Store {
  constructor(db) {
    this.db = db;
    this.db.exec('CREATE TABLE t (id)');
  }
}
function run(re, s) {
  return re.exec(s);
}`,
    }];
    const risky = await collectRiskySurfaces(jsFiles, 'treesitter');
    expect(risky.some((r) => r.target.toLowerCase().includes('exec'))).toBe(false);
  });

  it('flags bare exec/spawn calls AND qualified child_process.exec/cp.spawn', async () => {
    const jsFiles: SourceFile[] = [{
      path: 'src/run.js',
      content: `function a(cmd) { exec(cmd); }
function b(cmd) { spawn(cmd); }
function c(cmd) { child_process.exec(cmd); }
function d(cmd) { cp.spawn(cmd); }`,
    }];
    const risky = await collectRiskySurfaces(jsFiles, 'treesitter');
    const targets = risky.map((r) => r.target.toLowerCase());
    expect(targets).toContain('exec');
    expect(targets).toContain('spawn');
    expect(targets).toContain('child_process.exec');
    expect(targets).toContain('cp.spawn');
  });

  it('Python: flags os.system/pickle.loads (qualified, receiver-specific) but NOT json.loads (precision — same bare property name, different receiver)', async () => {
    const pyFiles: SourceFile[] = [{
      path: 'src/run.py',
      content: `import os, json, pickle
def run(cmd, raw, blob):
    os.system(cmd)
    data = json.loads(raw)
    obj = pickle.loads(blob)
    return data, obj
`,
    }];
    const risky = await collectRiskySurfaces(pyFiles, 'treesitter');
    const targets = risky.map((r) => r.target.toLowerCase());
    expect(targets).toContain('os.system');
    expect(targets).toContain('pickle.loads');
    expect(risky.some((r) => r.target.toLowerCase() === 'json.loads')).toBe(false);
    expect(risky.some((r) => r.target.toLowerCase() === 'loads')).toBe(false);
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
    for (const h of ['## 1.', '## 2.', '## 3.', '## 4.', '## 5.', '## 6.', '## 7.']) expect(md).toContain(h);
    expect(md).toContain('strcpy');
  });

  it('finds dead-code candidates: zero-fan-in functions, sorted, capped', async () => {
    const graph = await buildGraphRowsAst('repo', FILES);
    const stats = computeFnStats(graph);
    const dead = findDeadCodeCandidates(stats);
    // `run` and `twice` are never called by anything else in the repo -> fan_in 0.
    // `helper` IS called (by twice and run) -> fan_in > 0 -> not a candidate.
    expect(dead.some((f) => f.name === 'run')).toBe(true);
    expect(dead.some((f) => f.name === 'twice')).toBe(true);
    expect(dead.some((f) => f.name === 'helper')).toBe(false);
  });

  it('secrets section renders findings; dead-code section renders candidates', { timeout: 20000 }, async () => {
    const jsFiles: SourceFile[] = [{
      path: 'src/config.js',
      content: `function unused() { return 1; }
const stripeKey = '${FAKE_STRIPE_KEY}';
function main() { return 2; }
`,
    }];
    const graph = await buildGraphRowsAst('repo', jsFiles);
    const compressed = await compressTreeAsync('repo', jsFiles, 'T', 'treesitter');
    const ident = buildIdentity(compressed);
    const stats = computeFnStats(graph);
    const hot = buildHotspots(compressed, stats);
    const risky = await collectRiskySurfaces(jsFiles, 'treesitter');
    const dead = findDeadCodeCandidates(stats);
    const secrets = await collectSecretFindings(jsFiles);

    expect(secrets.length).toBeGreaterThanOrEqual(1);
    expect(dead.some((f) => f.name === 'unused')).toBe(true);

    const md = renderReport('repo', ident, graph, hot, risky, 'treesitter', [], secrets, dead);
    expect(md).toContain('possible credential(s) found');
    expect(md).toContain('Rotate every credential');
    expect(md).toContain('src/config.js:2');
    expect(md).toContain('zero in-repo callers');
    expect(md).toContain('`unused`');
  });

  it('empty secrets/dead-code render an honest "none found" line, not a blank section', async () => {
    const graph = await buildGraphRowsAst('repo', FILES);
    const compressed = await compressTreeAsync('repo', FILES, 'T', 'treesitter');
    const ident = buildIdentity(compressed);
    const hot = buildHotspots(compressed, computeFnStats(graph));
    const md = renderReport('repo', ident, graph, hot, [], 'treesitter', [], [], []);
    expect(md).toContain('no hardcoded credentials detected');
    expect(md).toContain('no zero-fan-in functions found');
  });
});

describe('modernize dossier · end-to-end', () => {
  // modernizeRepo now also runs the secretlint engine (cold-start init cost),
  // and this test calls it twice — give it headroom past vitest's 5s default.
  it('writes all three artifacts and a content-addressed receipt', { timeout: 20000 }, async () => {
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
      expect(receipt.data.dead_code_candidates).toBeGreaterThanOrEqual(1);
      expect(typeof receipt.data.possible_secrets).toBe('number');

      for (const f of ['symbolic_map.json', 'dependency_graph.json', 'MODERNIZATION_REPORT.md']) {
        await expect(fs.stat(path.join(out, f))).resolves.toBeTruthy();
      }

      // the deliverable: a real zip a customer can open, plus a sealed receipt.
      const pkg = receipt.data.package as { zip_path: string; zip_bytes: number };
      expect(pkg.zip_bytes).toBeGreaterThan(0);
      await expect(fs.stat(pkg.zip_path)).resolves.toBeTruthy();
      const zipHead = await fs.readFile(pkg.zip_path);
      expect(zipHead.subarray(0, 2).toString('latin1')).toBe('PK');

      const seal = receipt.data.seal as { sealed: boolean; sealed_path?: string; sha256?: string };
      expect(seal.sealed).toBe(true);
      expect(seal.sha256).toMatch(/^[0-9a-f]{64}$/);
      await expect(fs.stat(seal.sealed_path!)).resolves.toBeTruthy();

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
