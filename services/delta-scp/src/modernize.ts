// Delta SCP · source-repo modernization dossier
//
// The compressor turns a repo into a symbolic map and the graph builder into a
// call graph. This module is the source-side analogue of binre's modernize layer:
// it turns those into a modernization DELIVERABLE — what the repo is, its call-
// graph hotspots, its risk surfaces, and a roadmap — so a team facing a large,
// unfamiliar, legacy codebase has an entry point instead of a wall of files.
//
// Best fidelity comes from the tree-sitter extractor (real symbols for C/C++/C#/
// Java/... + a real call graph); it falls back to regex when unavailable. Output:
//
//   symbolic_map.json        the compressed symbolic map (compressTreeAsync)
//   dependency_graph.json    ast_nodes + ast_edges (calls + imports) + fan-in/out
//   MODERNIZATION_REPORT.md   identity · structure · hotspots · risk · roadmap
//
// Pure builders + thin I/O, mirroring the rest of the service.

import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { compressTreeAsync, type CompressedState, type SourceFile } from './compressor.js';
import { buildGraphRows, buildGraphRowsAst, type GraphRows, type NodeKey } from './graph.js';
import { fetchSourceFilesDetailed, type SkippedFile } from './source.js';
import { loadConfig, type ScpConfig } from './config.js';

export const DOSSIER_VERSION = 'modernize.v1';

// Call targets that mark a surface a modernization team should review first:
// injection/exec, unsafe C string ops, dynamic loading, unsafe deserialization,
// DOM-injection. Matched by the (lowercased) callee name from the call graph.
const RISKY_CALL_TARGETS = new Set([
  // exec / injection
  'eval', 'exec', 'execsync', 'system', 'popen', 'spawn', 'spawnsync', 'execfile',
  // unsafe C string / memory
  'strcpy', 'strcat', 'sprintf', 'vsprintf', 'gets', 'scanf', 'memcpy', 'alloca',
  // dynamic loading
  'dlopen', 'loadlibrary', 'loadlibrarya', 'loadlibraryw', 'getprocaddress',
  // unsafe deserialization
  'unserialize', 'unmarshal', 'loads', 'load_pickle',
  // DOM injection
  'dangerouslysetinnerhtml', 'innerhtml',
]);

// Languages that typically anchor a legacy-modernization engagement.
const LEGACY_LANGS = new Set(['c', 'cpp', 'csharp', 'java']);

const keyId = (k: NodeKey): string => `${k.file_path}|${k.name}|${k.node_type}`;

export interface FnStat {
  name: string;
  file: string;
  line: number | null;
  fan_in: number;
  fan_out: number;
}

// Fan-in / fan-out per function node, from the resolved `calls` edges.
export function computeFnStats(graph: GraphRows): Map<string, FnStat> {
  const stats = new Map<string, FnStat>();
  for (const n of graph.nodes) {
    if (n.node_type !== 'function') continue;
    stats.set(keyId({ file_path: n.file_path, name: n.name, node_type: 'function' }), {
      name: n.name, file: n.file_path, line: n.start_line, fan_in: 0, fan_out: 0,
    });
  }
  for (const e of graph.edges) {
    if (e.edge_type !== 'calls') continue;
    const s = stats.get(keyId(e.source));
    const t = stats.get(keyId(e.target));
    if (s) s.fan_out += 1;
    if (t) t.fan_in += 1;
  }
  return stats;
}

export interface Hotspots {
  core_utilities: FnStat[]; // highest fan-in — anchor a rewrite here
  orchestrators: FnStat[]; // highest fan-out — map a subsystem's control flow
  god_files: Array<{ path: string; language: string; symbols: number }>;
}

export function buildHotspots(compressed: CompressedState, stats: Map<string, FnStat>, top = 15): Hotspots {
  const fns = [...stats.values()];
  const core = [...fns].sort((a, b) => b.fan_in - a.fan_in || a.name.localeCompare(b.name))
    .filter((f) => f.fan_in > 0).slice(0, top);
  const orchestrators = [...fns].sort((a, b) => b.fan_out - a.fan_out || a.name.localeCompare(b.name))
    .filter((f) => f.fan_out > 0).slice(0, top);
  const god_files = compressed.symbolic_nodes
    .map((n) => ({ path: n.path, language: n.language, symbols: n.symbols.length }))
    .sort((a, b) => b.symbols - a.symbols)
    .filter((f) => f.symbols > 0)
    .slice(0, top);
  return { core_utilities: core, orchestrators, god_files };
}

export interface RiskySurface { file: string; caller: string; target: string }

// Risky call surfaces from RAW call pairs (external targets the graph drops when
// resolving edges are exactly the risky ones — eval/system/strcpy live in libc/
// stdlib, not the repo — so we read the unresolved pairs directly).
export async function collectRiskySurfaces(
  files: SourceFile[], extractor: 'regex' | 'treesitter',
): Promise<RiskySurface[]> {
  if (extractor !== 'treesitter') return [];
  const { extractCallEdgesAst, supportsAst } = await import('./treesitter.js');
  const { languageForPath } = await import('./compressor.js');
  const out: RiskySurface[] = [];
  for (const f of files) {
    const lang = languageForPath(f.path);
    if (!supportsAst(lang)) continue;
    try {
      for (const e of await extractCallEdgesAst(f.content, lang)) {
        if (RISKY_CALL_TARGETS.has(e.target.toLowerCase())) {
          out.push({ file: f.path, caller: e.source, target: e.target });
        }
      }
    } catch { /* fail-soft: skip this file's risk scan */ }
  }
  out.sort((a, b) => a.file.localeCompare(b.file) || a.caller.localeCompare(b.caller));
  return out;
}

export interface Identity {
  files: number;
  bytes: number;
  raw_tokens: number;
  compressed_tokens: number;
  compression_ratio: number;
  languages: Record<string, number>;
  legacy_languages: string[]; // legacy-heavy langs present, by file count desc
  total_symbols: number;
}

export function buildIdentity(compressed: CompressedState): Identity {
  const counts: Record<string, number> = { function: 0, class: 0, interface: 0 };
  let totalSymbols = 0;
  for (const n of compressed.symbolic_nodes) totalSymbols += n.symbols.length;
  const legacy = Object.entries(compressed.languages)
    .filter(([l]) => LEGACY_LANGS.has(l))
    .sort((a, b) => b[1] - a[1])
    .map(([l]) => l);
  return {
    files: compressed.stats.files_included,
    bytes: compressed.stats.bytes,
    raw_tokens: compressed.stats.raw_tokens_est,
    compressed_tokens: compressed.stats.compressed_tokens_est,
    compression_ratio: compressed.stats.compression_ratio,
    languages: compressed.languages,
    legacy_languages: legacy,
    total_symbols: totalSymbols,
  };
}

function countByType(graph: GraphRows): Record<string, number> {
  const c: Record<string, number> = {};
  for (const n of graph.nodes) c[n.node_type] = (c[n.node_type] ?? 0) + 1;
  return c;
}

export function renderReport(
  repo: string, ident: Identity, graph: GraphRows, hot: Hotspots, risky: RiskySurface[],
  extractor: 'regex' | 'treesitter', skipped: SkippedFile[] = [],
): string {
  const L: string[] = [];
  const types = countByType(graph);
  const callEdges = graph.edges.filter((e) => e.edge_type === 'calls').length;
  const importEdges = graph.edges.filter((e) => e.edge_type === 'imports').length;
  const langList = Object.entries(ident.languages).sort((a, b) => b[1] - a[1])
    .map(([l, n]) => `${l} (${n})`).join(', ');

  L.push(`# Modernization Dossier · ${repo}`);
  L.push('');
  L.push(`- extractor: **${extractor}**${extractor === 'regex' ? ' (run with SCP_EXTRACTOR=treesitter for the call graph + full symbols)' : ''}`);
  L.push('');

  L.push('## 1. What this codebase is');
  L.push('');
  L.push(`- ${ident.files} source files · ${(ident.bytes / 1024).toFixed(0)} KiB · ${ident.total_symbols} top-level symbols`);
  L.push(`- languages: ${langList}`);
  if (ident.legacy_languages.length) {
    L.push(`- **legacy-heavy languages present:** ${ident.legacy_languages.join(', ')} — these typically anchor the engagement.`);
  }
  L.push(`- symbolic compression: ${ident.raw_tokens} → ${ident.compressed_tokens} est. tokens (ratio ${ident.compression_ratio}) — the whole repo fits an LLM context as this map.`);
  const unsupported = skipped.filter((s) => s.reason === 'unsupported-ext');
  const oversize = skipped.filter((s) => s.reason === 'too-large');
  if (unsupported.length) {
    const byExt = new Map<string, number>();
    for (const s of unsupported) byExt.set(s.ext || '(no ext)', (byExt.get(s.ext || '(no ext)') ?? 0) + 1);
    const tally = [...byExt.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([e, n]) => `${e}×${n}`).join(' · ');
    L.push(`- **coverage: ${unsupported.length} file(s) NOT analyzed** (unsupported type): ${tally}. This dossier describes only the analyzable set above.`);
  }
  if (oversize.length) {
    L.push(`- **${oversize.length} file(s) skipped** (exceeded size cap): ${oversize.slice(0, 5).map((s) => s.path).join(', ')}${oversize.length > 5 ? ', …' : ''}`);
  }
  L.push('');

  L.push('## 2. Structure');
  L.push('');
  L.push(`- ${types.function ?? 0} functions · ${types.class ?? 0} classes · ${types.interface ?? 0} interfaces · ${types.type_definition ?? 0} types`);
  L.push(`- call graph: **${callEdges} call edges** · ${importEdges} import edges`);
  if (extractor !== 'treesitter') {
    L.push('- (call edges require the tree-sitter extractor; this run used regex.)');
  }
  L.push('');

  L.push('## 3. Where to start reading (hotspots)');
  L.push('');
  L.push('**Core utilities** — highest fan-in; the most depended-on code, so it anchors any rewrite:');
  for (const f of hot.core_utilities.slice(0, 10)) {
    L.push(`- \`${f.name}\` (${f.file}:${f.line}) — called by ${f.fan_in}`);
  }
  if (!hot.core_utilities.length) L.push('- _(no internal call edges resolved — run with tree-sitter)_');
  L.push('');
  L.push('**Orchestrators** — highest fan-out; these map a subsystem\'s control flow:');
  for (const f of hot.orchestrators.slice(0, 10)) {
    L.push(`- \`${f.name}\` (${f.file}:${f.line}) — calls ${f.fan_out}`);
  }
  if (!hot.orchestrators.length) L.push('- _(none)_');
  L.push('');
  L.push('**Largest files** — most symbols; likely god-objects to decompose:');
  for (const f of hot.god_files.slice(0, 10)) {
    L.push(`- \`${f.path}\` (${f.language}) — ${f.symbols} symbols`);
  }
  L.push('');

  L.push('## 4. Risk surfaces');
  L.push('');
  if (risky.length) {
    L.push(`**${risky.length} review-first call sites** (exec/injection · unsafe C string ops · dynamic loading · unsafe deserialization · DOM injection):`);
    for (const r of risky.slice(0, 25)) {
      L.push(`- \`${r.target}\` called by \`${r.caller}\` (${r.file})`);
    }
    if (risky.length > 25) L.push(`- …and ${risky.length - 25} more`);
  } else if (extractor !== 'treesitter') {
    L.push('- risk scan requires the tree-sitter extractor (call graph); this run used regex.');
  } else {
    L.push('- no review-first call sites detected.');
  }
  L.push('');

  L.push('## 5. Modernization roadmap');
  L.push('');
  L.push('1. **Read the orchestrators, rewrite the core utilities.** Section 3 orders the codebase by dependency: orchestrators are the map, core utilities are the load-bearing walls. Rewrite core utilities first behind characterization tests — they de-risk everything downstream.');
  L.push('2. **Decompose the god-files.** The largest-by-symbol files (Section 3) concentrate the most surface area; split them along the call graph before porting.');
  L.push('3. **Quarantine the risk surfaces** (Section 4): exec/injection, unsafe C string ops, dynamic loading, and unsafe deserialization rarely survive a lift-and-shift. Wrap each behind a thin adapter, then replace with a supported, audited equivalent.');
  if (ident.legacy_languages.length) {
    L.push(`4. **Plan the legacy-language exit.** ${ident.legacy_languages.join('/')} carry the modernization weight here — decide per subsystem: retarget in place, port, or rewrite, using the call graph to size the blast radius.`);
  }
  L.push(`${ident.legacy_languages.length ? 5 : 4}. **Re-run this dossier as you go.** It is deterministic — a re-run on the same tree reproduces the map, so you can track the call graph and risk surface shrinking as the rewrite lands.`);
  L.push('');
  L.push('---');
  L.push(`_Generated by delta-scp modernize · ${DOSSIER_VERSION} · extractor=${extractor}._`);
  return L.join('\n') + '\n';
}

// Content-address the dossier by the symbolic map (minus the wall-clock stamp).
function contentSha(compressed: CompressedState): string {
  const { generated_at, ...rest } = compressed;
  return createHash('sha256').update(JSON.stringify(rest)).digest('hex');
}

export interface DossierReceipt {
  tool: 'delta-scp-modernize';
  op: 'modernize';
  dossier_version: string;
  sha256: string;
  status: 'ok';
  data: Record<string, unknown>;
}

export async function modernizeRepo(
  repoUrl: string, outDir: string, config: ScpConfig = loadConfig(),
): Promise<DossierReceipt> {
  const { files, skipped } = await fetchSourceFilesDetailed(repoUrl, config);
  const generatedAt = new Date().toISOString();
  const compressed = await compressTreeAsync(repoUrl, files, generatedAt, config.extractor);
  const graph = config.extractor === 'treesitter'
    ? await buildGraphRowsAst(repoUrl, files)
    : buildGraphRows(repoUrl, files);

  const ident = buildIdentity(compressed);
  const stats = computeFnStats(graph);
  const hot = buildHotspots(compressed, stats);
  const risky = await collectRiskySurfaces(files, config.extractor);
  const report = renderReport(repoUrl, ident, graph, hot, risky, config.extractor, skipped);

  await fs.mkdir(outDir, { recursive: true });
  await fs.writeFile(path.join(outDir, 'symbolic_map.json'), JSON.stringify(compressed, null, 2));
  await fs.writeFile(path.join(outDir, 'dependency_graph.json'), JSON.stringify(graph, null, 2));
  await fs.writeFile(path.join(outDir, 'MODERNIZATION_REPORT.md'), report);

  return {
    tool: 'delta-scp-modernize',
    op: 'modernize',
    dossier_version: DOSSIER_VERSION,
    sha256: contentSha(compressed),
    status: 'ok',
    data: {
      out_dir: outDir,
      extractor: config.extractor,
      identity: ident,
      call_edges: graph.edges.filter((e) => e.edge_type === 'calls').length,
      hotspot_counts: {
        core_utilities: hot.core_utilities.length,
        orchestrators: hot.orchestrators.length,
        god_files: hot.god_files.length,
      },
      risky_surfaces: risky.length,
      skipped_files: skipped.length,
    },
  };
}

// CLI: npm run modernize -- <repo> [--out dir]
async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const positionals: string[] = [];
  let out: string | undefined;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--out') out = argv[++i];
    else positionals.push(argv[i]);
  }
  const target = positionals[0];
  if (!target) {
    console.error('usage: npm run modernize -- <repo> [--out dir]   (set SCP_EXTRACTOR=treesitter for the call graph)');
    process.exit(2);
  }
  const config = loadConfig();
  const outDir = out ?? path.join(process.cwd(), 'modernize-out',
    createHash('sha256').update(target).digest('hex').slice(0, 12));
  const receipt = await modernizeRepo(target, outDir, config);
  console.log(JSON.stringify(receipt));
}

// Run main() only as a script, not on import (tests import named exports). Compare
// resolved paths — the `file://${argv[1]}` idiom is broken on Windows (argv[1] is a
// backslash path, never equal to the file:// URL).
const entry = process.argv[1] ? path.resolve(process.argv[1]) : '';
if (entry && entry === path.resolve(fileURLToPath(import.meta.url))) {
  main().catch((err) => {
    console.error('[delta-scp] modernize error:', err);
    process.exit(1);
  });
}
