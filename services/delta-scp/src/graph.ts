// Delta SCP · AST graph builder + persistence (the Supabase ingestion side)
//
// buildGraphRows is the pure bridge: it turns a repo's source files into
// ast_nodes / ast_edges rows for migration 006's schema, reusing the engine's
// existing symbol extractor (no new parser). File + symbol nodes are exact;
// edges are limited to `imports`, resolved best-effort within the repo.
//
// FIDELITY SEAM: calls / inherits / implements / instantiates edges, and precise
// symbol bodies, require a true AST. That is a tree-sitter pass — the canonical
// tool for multi-language parsing — slotted in here later. Regex gives us a
// populated graph today; tree-sitter raises edge fidelity without changing the
// schema, the reader, or the prune/flue stages downstream.
//
// persistGraph / readFocusFromGraph are thin Supabase I/O (kept untested at unit
// level, matching source.ts) wrapping the pure builder + the schema.

import type { SupabaseClient } from '@supabase/supabase-js';
import { createHash } from 'node:crypto';
import path from 'node:path';
import {
  extractSymbols,
  languageForPath,
  type SourceFile,
  type SymbolEntry,
} from './compressor.js';

// Maps the extractor's loose `kind` onto the schema's node_type enum.
const KIND_TO_NODE_TYPE: Record<string, string> = {
  class: 'class',
  interface: 'interface',
  function: 'function',
  def: 'function',
  func: 'function',
  fn: 'function',
  method: 'function',
  type: 'type_definition',
  enum: 'type_definition',
  struct: 'type_definition',
  trait: 'type_definition',
  const: 'variable',
  var: 'variable',
};

export interface AstNodeRow {
  repo_name: string;
  node_type: string;
  name: string;
  file_path: string;
  start_line: number | null;
  end_line: number | null;
  raw_signature: string | null;
  checksum: string | null;
  metadata: Record<string, unknown>;
}

/** Node identity (the UNIQUE key from migration 006), used to wire edges pre-UUID. */
export interface NodeKey {
  file_path: string;
  name: string;
  node_type: string;
}

export interface AstEdgeRow {
  source: NodeKey;
  target: NodeKey;
  edge_type: string;
  weight: number;
}

export interface GraphRows {
  nodes: AstNodeRow[];
  edges: AstEdgeRow[];
}

const JS_EXTS = ['ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs'];

// import/require/export-from specifiers (TS/JS) and import/from (Python).
const JS_IMPORT_RE = /(?:import|export)[^'"]*?from\s*['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)/g;
const PY_IMPORT_RE = /^\s*(?:from\s+([.\w]+)\s+import|import\s+([.\w]+))/gm;

function basename(p: string): string {
  return p.split('/').pop() ?? p;
}

// Resolve a JS/TS relative specifier to a known repo file (try extensions + index).
function resolveJsImport(fromFile: string, spec: string, known: Set<string>): string | null {
  if (!spec.startsWith('.')) return null; // bare package => external, no node
  const baseDir = path.posix.dirname(fromFile);
  const joined = path.posix.normalize(path.posix.join(baseDir, spec));
  const candidates = [
    joined,
    ...JS_EXTS.map((e) => `${joined}.${e}`),
    ...JS_EXTS.map((e) => `${joined}/index.${e}`),
  ];
  return candidates.find((c) => known.has(c)) ?? null;
}

// Resolve a Python dotted module to a known repo file (module.py or pkg/__init__.py).
function resolvePyImport(spec: string, known: Set<string>): string | null {
  const rel = spec.replace(/^\.+/, '').replace(/\./g, '/');
  if (!rel) return null;
  const candidates = [`${rel}.py`, `${rel}/__init__.py`];
  return candidates.find((c) => known.has(c)) ?? null;
}

/**
 * Pure: source files -> ast_nodes + ast_edges rows. Deterministic (stable file
 * ordering). Edges only emitted when their target resolves to a known repo file.
 */
export function buildGraphRows(repoName: string, files: SourceFile[]): GraphRows {
  const sorted = [...files].sort((a, b) => a.path.localeCompare(b.path));
  const known = new Set(sorted.map((f) => f.path));
  const nodes: AstNodeRow[] = [];
  const edges: AstEdgeRow[] = [];
  const fileKey = (p: string): NodeKey => ({ file_path: p, name: basename(p), node_type: 'file' });

  for (const file of sorted) {
    const language = languageForPath(file.path);
    const lines = file.content.split('\n');

    // File node.
    nodes.push({
      repo_name: repoName,
      node_type: 'file',
      name: basename(file.path),
      file_path: file.path,
      start_line: null,
      end_line: lines.length,
      raw_signature: null,
      checksum: createHash('sha256').update(file.content).digest('hex'),
      metadata: { language },
    });

    // Symbol nodes (reuse the existing extractor).
    const symbols: SymbolEntry[] = extractSymbols(file.content, language);
    for (const sym of symbols) {
      nodes.push({
        repo_name: repoName,
        node_type: KIND_TO_NODE_TYPE[sym.kind] ?? 'variable',
        name: sym.name,
        file_path: file.path,
        start_line: sym.line,
        end_line: sym.line,
        raw_signature: (lines[sym.line - 1] ?? '').trim().slice(0, 500) || null,
        checksum: null,
        metadata: { kind: sym.kind, language },
      });
    }

    // Import edges (file -> file), best-effort within the repo.
    const isJs = JS_EXTS.includes(file.path.split('.').pop()?.toLowerCase() ?? '');
    const isPy = language === 'python';
    if (isJs) {
      for (const m of file.content.matchAll(JS_IMPORT_RE)) {
        const spec = m[1] ?? m[2];
        const target = spec && resolveJsImport(file.path, spec, known);
        if (target) edges.push({ source: fileKey(file.path), target: fileKey(target), edge_type: 'imports', weight: 1 });
      }
    } else if (isPy) {
      for (const m of file.content.matchAll(PY_IMPORT_RE)) {
        const spec = m[1] ?? m[2];
        const target = spec && resolvePyImport(spec, known);
        if (target) edges.push({ source: fileKey(file.path), target: fileKey(target), edge_type: 'imports', weight: 1 });
      }
    }
  }

  // De-dup nodes by identity (file_path|name|node_type) — the schema's UNIQUE
  // key. Two same-named symbols of the same kind in one file (TS declaration
  // merging, Python overloads, conditional defs) collapse to one, keeping a
  // plain insert from tripping the unique constraint. First occurrence wins.
  const nodeSeen = new Set<string>();
  const dedupedNodes = nodes.filter((n) => {
    const k = `${n.file_path}|${n.name}|${n.node_type}`;
    if (nodeSeen.has(k)) return false;
    nodeSeen.add(k);
    return true;
  });

  // De-dup edges (same source/target/type) so the insert doesn't churn.
  const seen = new Set<string>();
  const dedupedEdges = edges.filter((e) => {
    const k = `${e.source.file_path}>${e.target.file_path}:${e.edge_type}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });

  return { nodes: dedupedNodes, edges: dedupedEdges };
}

const keyId = (k: NodeKey) => `${k.file_path}|${k.name}|${k.node_type}`;

export interface ResolvedEdgeRow {
  source_id: string;
  target_id: string;
  edge_type: string;
  weight: number;
}

/**
 * Pure: map identity-keyed edges onto DB rows via the node-id index. An edge is
 * resolved by the FULL node identity (file_path|name|node_type), never by name
 * alone — so a `imports` edge to `src/b/index.ts` can't collide with `src/c/
 * index.ts`. Edges whose endpoints aren't in the index (external packages,
 * unindexed files) are dropped — the graph holds only edges between known nodes.
 *
 * Tested directly: this is the correctness-critical step (a name-only mapping
 * silently mis-wires or drops cross-file edges).
 */
export function resolveEdgeRows(
  edges: AstEdgeRow[],
  idByKey: Map<string, string>,
): ResolvedEdgeRow[] {
  return edges
    .map((e) => {
      const source_id = idByKey.get(keyId(e.source));
      const target_id = idByKey.get(keyId(e.target));
      return source_id && target_id
        ? { source_id, target_id, edge_type: e.edge_type, weight: e.weight }
        : null;
    })
    .filter((e): e is ResolvedEdgeRow => e !== null);
}

/**
 * Sync a repo's graph into Supabase with a repo-scoped delete-and-replace:
 *
 *   1. delete every ast_node for this repo  (ON DELETE CASCADE clears its edges)
 *   2. insert all current nodes, returning their fresh ids
 *   3. resolve edges against the full node set, then insert them
 *
 * Idempotent — a re-run reflects the repo exactly as it is now, dropping rows
 * for files/symbols that no longer exist (the gap a plain upsert leaves). It is
 * deliberately repo-scoped, NOT per-file: every node exists before any edge is
 * mapped, so cross-file `imports` edges resolve. A per-file sync cannot see the
 * other file's nodes and would silently drop those edges.
 *
 * Thin I/O over buildGraphRows + resolveEdgeRows. The delete+insert is not a
 * transaction here, so a mid-sync failure can leave the repo's graph empty until
 * the next job repopulates it — acceptable for a secondary index that the worker
 * already rebuilds fail-soft on every job.
 */
export async function persistGraph(
  db: SupabaseClient,
  repoName: string,
  rows: GraphRows,
): Promise<{ nodes: number; edges: number }> {
  // 1. Drop the repo's existing nodes; CASCADE removes their edges.
  const { error: delErr } = await db.from('ast_nodes').delete().eq('repo_name', repoName);
  if (delErr) throw new Error(`persistGraph delete failed: ${delErr.message}`);

  if (rows.nodes.length === 0) return { nodes: 0, edges: 0 };

  // 2. Insert nodes, returning ids in one round trip (no separate read-back).
  const { data: inserted, error: nodeErr } = await db
    .from('ast_nodes')
    .insert(rows.nodes)
    .select('id,file_path,name,node_type');
  if (nodeErr || !inserted) {
    throw new Error(`persistGraph insert nodes failed: ${nodeErr?.message ?? 'no rows returned'}`);
  }

  const idByKey = new Map<string, string>();
  for (const r of inserted as Array<{ id: string; file_path: string; name: string; node_type: string }>) {
    idByKey.set(keyId({ file_path: r.file_path, name: r.name, node_type: r.node_type }), r.id);
  }

  // 3. Resolve + insert edges against the full node set.
  const edgeRows = resolveEdgeRows(rows.edges, idByKey);
  if (edgeRows.length > 0) {
    const { error: edgeErr } = await db.from('ast_edges').insert(edgeRows);
    if (edgeErr) throw new Error(`persistGraph insert edges failed: ${edgeErr.message}`);
  }

  return { nodes: rows.nodes.length, edges: edgeRows.length };
}

/**
 * Read a focus set from the graph: the files mentioned in `focusPaths` plus their
 * direct import-neighbours (one hop, either direction). Returns repo-relative
 * file paths — the anchor `paths` the prune stage consumes, without ever touching
 * the filesystem. This is the "ingest from Supabase instead of the file tree"
 * path: the agent names what it's touching; the graph returns the closure.
 */
export async function readFocusFromGraph(
  db: SupabaseClient,
  repoName: string,
  focusPaths: string[],
): Promise<string[]> {
  if (focusPaths.length === 0) return [];
  const focus = new Set(focusPaths.map((p) => p.replace(/\\/g, '/')));

  // File-node ids for the focus paths.
  const { data: focusNodes, error } = await db
    .from('ast_nodes')
    .select('id,file_path')
    .eq('repo_name', repoName)
    .eq('node_type', 'file')
    .in('file_path', [...focus]);
  if (error) throw new Error(`readFocusFromGraph failed: ${error.message}`);

  const ids = (focusNodes ?? []).map((n: { id: string }) => n.id);
  if (ids.length === 0) return [...focus];

  // One-hop import neighbours via the resolved view.
  const { data: edges, error: edgeErr } = await db
    .from('codebase_graph_view')
    .select('source_path,target_path,source_id,target_id')
    .eq('repo_name', repoName)
    .or(`source_id.in.(${ids.join(',')}),target_id.in.(${ids.join(',')})`);
  if (edgeErr) throw new Error(`readFocusFromGraph neighbours failed: ${edgeErr.message}`);

  const out = new Set<string>(focus);
  for (const e of (edges ?? []) as Array<{ source_path: string; target_path: string }>) {
    out.add(e.source_path);
    out.add(e.target_path);
  }
  return [...out];
}
