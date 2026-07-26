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
import { collectSecretFindings, type SecretFinding } from './secrets.js';
import { bundleDeployablePackage, sealArtifact } from './packaging.js';

export const DOSSIER_VERSION = 'modernize.v1';

// Call targets that mark a surface a modernization team should review first,
// matched by the (lowercased) callee name on ANY call shape — bare identifier
// OR member/attribute call. Safe to match unconditionally because these names
// are essentially never legitimate as an ordinary method on an unrelated
// object: unsafe C string / memory ops, dynamic loading, unambiguous
// deserialization, and call-form DOM injection.
const RISKY_CALL_TARGETS = new Set([
  'eval',
  // unsafe C string / memory
  'strcpy', 'strcat', 'sprintf', 'vsprintf', 'gets', 'scanf', 'memcpy', 'alloca',
  // dynamic loading
  'dlopen', 'loadlibrary', 'loadlibrarya', 'loadlibraryw', 'getprocaddress',
  // unsafe deserialization (unambiguous names)
  'unserialize', 'unmarshal', 'load_pickle',
  // DOM injection (call-form: dangerouslySetInnerHTML(...) as a function/prop-call)
  'dangerouslysetinnerhtml', 'innerhtml',
]);

// Exec/injection + generic-deserialization names that COLLIDE with common,
// benign method names once member/attribute calls are in scope (added by the
// JS-sink fix): RegExp.exec(), better-sqlite3's Database.exec(), json.loads()
// vs pickle.loads(), etc. Found live 2026-07-14 running the dossier against a
// real production repo (delta-kernel) — `this.db.exec(DDL)`, a SQLite
// schema-exec call, was misflagged as shell-exec/injection risk. Matched ONLY
// as a BARE identifier call here (`import { exec } from 'child_process'; exec(x)`
// — unambiguous without a receiver); member/attribute calls with these names
// are matched ONLY via the receiver-qualified pairs in RISKY_QUALIFIED_TARGETS.
const EXEC_FAMILY_TARGETS = new Set([
  'exec', 'execsync', 'system', 'popen', 'spawn', 'spawnsync', 'execfile', 'loads',
]);

// DOM-injection sink PROPERTIES — `el.innerHTML = x`, not a call at all, so
// RISKY_CALL_TARGETS (matched against call edges) can never see it. This is the
// dominant real-world JS/web XSS shape (see collectRiskySurfaces). Kept narrow
// (just the two raw-HTML-write properties) rather than also flagging e.g. `.href`
// or `.write` — those are common on ordinary, non-DOM objects (route configs,
// streams) and would drown real findings in false positives.
const DOM_SINK_PROPS = new Set(['innerhtml', 'outerhtml']);

// Qualified call targets — sinks that are only dangerous for a SPECIFIC
// receiver. A bare property/attribute name alone ('write', 'exec', 'loads',
// 'system') is far too generic to denylist against every member call (fs.write,
// res.write, a DB's .exec(), RegExp.exec(), json.loads are all ordinary and
// common) — matched against extractQualifiedCallEdgesAst's full receiver-chain
// text (e.g. "document.write", "this.db.exec"), lowercased. 'cp' covers the
// common `import * as cp from 'child_process'` alias.
const RISKY_QUALIFIED_TARGETS = new Set([
  'document.write', 'document.writeln',
  'child_process.exec', 'child_process.execsync', 'child_process.spawn',
  'child_process.spawnsync', 'child_process.execfile',
  'cp.exec', 'cp.execsync', 'cp.spawn', 'cp.spawnsync', 'cp.execfile',
  'os.system', 'os.popen',
  'subprocess.call', 'subprocess.run', 'subprocess.popen',
  'pickle.loads', 'pickle.load', 'marshal.loads',
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

// Functions nobody in the repo calls (fan_in === 0). NOT a claim of confirmed-dead
// code — an exported API, a framework entry point (route handler, event listener),
// or a call from outside the analyzed set (a test file, a caller in another repo)
// all show fan_in 0 too. Same "review-first candidate list" framing as risky
// surfaces: a human/Claude pass still has to confirm before deleting anything —
// this scanner never removes code itself (destructive, needs judgment a static
// call-graph can't supply).
export function findDeadCodeCandidates(stats: Map<string, FnStat>, top = 20): FnStat[] {
  return [...stats.values()]
    .filter((f) => f.fan_in === 0)
    .sort((a, b) => a.file.localeCompare(b.file) || a.name.localeCompare(b.name))
    .slice(0, top);
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

export interface RiskySurface { file: string; caller: string; target: string; kind: 'call' | 'assignment' }

// Risky surfaces from two structurally different AST shapes:
//   - CALLS: raw call pairs (external targets the graph drops when resolving
//     edges are exactly the risky ones — eval/system/strcpy live in libc/stdlib,
//     not the repo — so we read the unresolved pairs directly). Includes both
//     bare-identifier calls (eval(x)) and member/method calls (document.write(x)),
//     but exec-family names (exec/spawn/system/loads/...) only count as risky
//     bare — as a member call they need a specific dangerous receiver, checked
//     separately via RISKY_QUALIFIED_TARGETS (a bare '.exec()' could just as
//     easily be RegExp.exec() or a DB's schema-exec method).
//   - ASSIGNMENTS: property writes (el.innerHTML = x). Not a call at all — a
//     call-only scan is structurally blind to this, the dominant JS/web XSS shape.
export async function collectRiskySurfaces(
  files: SourceFile[], extractor: 'regex' | 'treesitter',
): Promise<RiskySurface[]> {
  if (extractor !== 'treesitter') return [];
  const { extractCallEdgesAst, extractQualifiedCallEdgesAst, extractPropertyAssignmentsAst, supportsAst } =
    await import('./treesitter.js');
  const { languageForPath } = await import('./compressor.js');
  const out: RiskySurface[] = [];
  for (const f of files) {
    const lang = languageForPath(f.path);
    if (!supportsAst(lang)) continue;
    try {
      for (const e of await extractCallEdgesAst(f.content, lang)) {
        const t = e.target.toLowerCase();
        // Unambiguous targets match any call shape; exec-family targets only
        // match as a BARE call — a qualified/member call needs a specific
        // dangerous receiver (RISKY_QUALIFIED_TARGETS below) to count.
        if (RISKY_CALL_TARGETS.has(t) || (!e.qualified && EXEC_FAMILY_TARGETS.has(t))) {
          out.push({ file: f.path, caller: e.source, target: e.target, kind: 'call' });
        }
      }
      for (const e of await extractQualifiedCallEdgesAst(f.content, lang)) {
        if (RISKY_QUALIFIED_TARGETS.has(e.target.toLowerCase())) {
          out.push({ file: f.path, caller: e.source, target: e.target, kind: 'call' });
        }
      }
      for (const a of await extractPropertyAssignmentsAst(f.content, lang)) {
        if (DOM_SINK_PROPS.has(a.property.toLowerCase())) {
          out.push({ file: f.path, caller: a.source ?? '(module scope)', target: a.property, kind: 'assignment' });
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
  secrets: SecretFinding[] = [], deadCode: FnStat[] = [],
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
    L.push(`**${risky.length} review-first surfaces** (exec/injection · unsafe C string ops · dynamic loading · unsafe deserialization · DOM injection):`);
    for (const r of risky.slice(0, 25)) {
      const desc = r.kind === 'assignment'
        ? `\`.${r.target}\` assigned in \`${r.caller}\` (${r.file})`
        : `\`${r.target}\` called by \`${r.caller}\` (${r.file})`;
      L.push(`- ${desc}`);
    }
    if (risky.length > 25) L.push(`- …and ${risky.length - 25} more`);
  } else if (extractor !== 'treesitter') {
    L.push('- risk scan requires the tree-sitter extractor (call graph); this run used regex.');
  } else {
    L.push('- no review-first call sites detected.');
  }
  L.push('');

  L.push('## 5. Secrets');
  L.push('');
  if (secrets.length) {
    L.push(`**${secrets.length} possible credential(s) found** — hardcoded, not environment-loaded (scanned via secretlint's recommend preset; source files only, see coverage note in Section 1 for what wasn't scanned):`);
    for (const s of secrets.slice(0, 25)) {
      L.push(`- ${s.message} (${s.file}:${s.line})`);
    }
    if (secrets.length > 25) L.push(`- …and ${secrets.length - 25} more`);
    L.push('- **Rotate every credential found here before or immediately after any code goes public.** A rewritten repo does not un-leak a key that was ever committed.');
  } else {
    L.push('- no hardcoded credentials detected in the analyzed source (does not cover .env/.pem/key files outside the analyzable set — see Section 1 coverage note).');
  }
  L.push('');

  L.push('## 6. Dead-code candidates');
  L.push('');
  if (deadCode.length) {
    L.push(`**${deadCode.length} function(s) with zero in-repo callers** — review before relying on this list; an exported API, a framework entry point (route/handler/listener), or a caller outside the analyzed set all show zero fan-in too. Not auto-removed:`);
    for (const f of deadCode.slice(0, 20)) {
      L.push(`- \`${f.name}\` (${f.file}${f.line != null ? ':' + f.line : ''})`);
    }
    if (deadCode.length > 20) L.push(`- …and ${deadCode.length - 20} more`);
  } else {
    L.push('- no zero-fan-in functions found (or the call graph is empty for this extractor).');
  }
  L.push('');

  L.push('## 7. Modernization roadmap');
  L.push('');
  L.push('1. **Read the orchestrators, rewrite the core utilities.** Section 3 orders the codebase by dependency: orchestrators are the map, core utilities are the load-bearing walls. Rewrite core utilities first behind characterization tests — they de-risk everything downstream.');
  L.push('2. **Decompose the god-files.** The largest-by-symbol files (Section 3) concentrate the most surface area; split them along the call graph before porting.');
  L.push('3. **Quarantine the risk surfaces and rotate any secrets** (Sections 4-5): exec/injection, unsafe C string ops, dynamic loading, and unsafe deserialization rarely survive a lift-and-shift — wrap each behind a thin adapter, then replace with a supported, audited equivalent. Any credential in Section 5 gets rotated regardless of what else changes.');
  L.push('4. **Confirm the dead-code candidates** (Section 6) against real usage — exported APIs and framework entry points are false positives; genuine dead code is safe to drop once confirmed.');
  if (ident.legacy_languages.length) {
    L.push(`5. **Plan the legacy-language exit.** ${ident.legacy_languages.join('/')} carry the modernization weight here — decide per subsystem: retarget in place, port, or rewrite, using the call graph to size the blast radius.`);
  }
  L.push(`${ident.legacy_languages.length ? 6 : 5}. **Re-run this dossier as you go.** It is deterministic — a re-run on the same tree reproduces the map, so you can track the call graph and risk surface shrinking as the rewrite lands.`);
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
  const secrets = await collectSecretFindings(files);
  const deadCode = findDeadCodeCandidates(stats);
  const report = renderReport(repoUrl, ident, graph, hot, risky, config.extractor, skipped, secrets, deadCode);

  await fs.mkdir(outDir, { recursive: true });
  await fs.writeFile(path.join(outDir, 'symbolic_map.json'), JSON.stringify(compressed, null, 2));
  await fs.writeFile(path.join(outDir, 'dependency_graph.json'), JSON.stringify(graph, null, 2));
  await fs.writeFile(path.join(outDir, 'MODERNIZATION_REPORT.md'), report);

  // The deliverable: one file a customer opens (dossier.zip), plus a sealed,
  // content-addressed receipt (dossier.zip.sgl) proving what was delivered.
  // Closes the gap the proof-run named — up to here this function produced a
  // MAP, not a package.
  const pkg = await bundleDeployablePackage(
    outDir, ['symbolic_map.json', 'dependency_graph.json', 'MODERNIZATION_REPORT.md'],
  );
  const seal = await sealArtifact(pkg.zip_path);

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
      possible_secrets: secrets.length,
      dead_code_candidates: deadCode.length,
      package: pkg,
      seal,
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
