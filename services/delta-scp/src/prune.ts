// Delta SCP · state-aware pruning
//
// Turns the static symbolic map into a *focused* one. Given anchor tokens — the
// files/symbols an agent is actively touching, plus the raw text of a live error
// or tool trace — it keeps the focus module (and its sibling files) at full
// symbol fidelity and aggressively collapses everything else to a one-line stub.
//
// This is the "state-aware" half of the v2 upgrade: instead of compressing a
// flat snapshot of a 5,000-file repo, it compresses the boilerplate *around* the
// live error and leaves the relevant code legible.
//
// Pure and deterministic — no I/O, no clock. Same (map, anchor) in => same out.
//
// Proximity note: with only the symbolic map in hand, "neighbour" means
// same-directory (a deterministic locality heuristic). True dependency
// neighbours (importers/callees) come from the AST graph reader (graph_source),
// which can hand richer anchors in via `paths`.

import type { CompressedState, SymbolicNode } from './compressor.js';
import { estimateTokens } from './compressor.js';

export type NodeTier = 'anchor' | 'neighbor' | 'context';

export interface AnchorSpec {
  /** Explicit file paths to anchor (repo-relative, any separator). */
  paths?: string[];
  /** Explicit symbol names to anchor (a node carrying one is promoted to anchor). */
  symbols?: string[];
  /** Raw error / tool-trace text; file paths mentioned in it become anchors. */
  trace?: string;
}

export interface PrunedNode extends SymbolicNode {
  tier: NodeTier;
  /** True when symbols were dropped to collapse this node to a stub. */
  collapsed: boolean;
  /** Original symbol count, preserved even when symbols are dropped. */
  symbol_count: number;
}

export interface PruneStats {
  anchored: boolean; // false => no anchors resolved, map returned unpruned
  anchor_nodes: number;
  neighbor_nodes: number;
  context_nodes: number;
  tokens_before: number; // compressed_tokens_est of the input map
  tokens_after: number; // compressed_tokens_est of the pruned map
  focus_yield: number; // tokens dropped by pruning (before - after)
  focus_ratio: number; // after / before, 4dp
}

export interface PrunedState extends Record<string, unknown> {
  protocol: 'DELTA_SCP';
  version: string;
  status: 'pruned';
  repo: string;
  generated_at: string;
  anchor: { paths: string[]; symbols: string[] };
  stats: PruneStats;
  languages: Record<string, number>;
  symbolic_nodes: PrunedNode[];
}

// Path tokens inside trace text: a run of path-ish chars ending in a known source
// extension, optionally followed by :line:col. Both / and \ separators.
const TRACE_PATH_RE =
  /[\w./\\-]+\.(?:ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|rb|php|c|h|cpp|hpp|cs|swift|kt|sql|sh)(?=[:)\s,'"]|$)/gi;

function normalizePath(p: string): string {
  return p.replace(/\\/g, '/').replace(/^\.\//, '').trim();
}

function dirOf(path: string): string {
  const i = path.lastIndexOf('/');
  return i === -1 ? '' : path.slice(0, i);
}

/** Extract repo-relative-ish path hints from raw trace text. */
export function extractTracePaths(trace: string): string[] {
  const out = new Set<string>();
  for (const m of trace.matchAll(TRACE_PATH_RE)) {
    out.add(normalizePath(m[0]));
  }
  return [...out];
}

// A node matches an anchor path when its path ends with the (normalized) anchor,
// or vice versa — so "src/auth/login.ts", "auth/login.ts", and "login.ts" all hit
// the same node regardless of how deep the trace quoted it.
function pathMatches(nodePath: string, anchor: string): boolean {
  const a = normalizePath(anchor);
  if (!a) return false;
  return (
    nodePath === a ||
    nodePath.endsWith('/' + a) ||
    a.endsWith('/' + nodePath) ||
    nodePath.split('/').pop() === a // bare basename
  );
}

/**
 * State-aware prune. Anchors are resolved from explicit paths/symbols plus any
 * paths found in the trace; the focus module's directory siblings become
 * neighbours; everything else collapses to a stub (symbols dropped).
 *
 * If nothing resolves to an anchor, the map is returned intact (all symbols
 * kept) with `anchored: false` — pruning never silently guts a map.
 */
export function pruneMap(map: CompressedState, anchor: AnchorSpec): PrunedState {
  const explicitPaths = (anchor.paths ?? []).map(normalizePath).filter(Boolean);
  const tracePaths = anchor.trace ? extractTracePaths(anchor.trace) : [];
  const anchorPaths = [...new Set([...explicitPaths, ...tracePaths])];
  const anchorSymbols = [...new Set((anchor.symbols ?? []).map((s) => s.trim()).filter(Boolean))];

  const isAnchorByPath = (p: string) => anchorPaths.some((a) => pathMatches(p, a));
  const symbolSet = new Set(anchorSymbols);
  const isAnchorBySymbol = (n: SymbolicNode) =>
    symbolSet.size > 0 && n.symbols.some((s) => symbolSet.has(s.name));

  // First pass: identify anchor nodes and the directories they live in.
  const anchorDirs = new Set<string>();
  const tier = new Map<string, NodeTier>();
  for (const n of map.symbolic_nodes) {
    if (isAnchorByPath(n.path) || isAnchorBySymbol(n)) {
      tier.set(n.path, 'anchor');
      anchorDirs.add(dirOf(n.path));
    }
  }

  const anchored = tier.size > 0;

  // Second pass: neighbours (same dir as an anchor), then context (the rest).
  for (const n of map.symbolic_nodes) {
    if (tier.has(n.path)) continue;
    tier.set(n.path, anchored && anchorDirs.has(dirOf(n.path)) ? 'neighbor' : 'context');
  }

  const languages: Record<string, number> = {};
  let anchorCount = 0;
  let neighborCount = 0;
  let contextCount = 0;

  const prunedNodes: PrunedNode[] = map.symbolic_nodes.map((n) => {
    const t = tier.get(n.path) ?? 'context';
    // Collapse context nodes only when we actually anchored — otherwise keep the
    // full map. Anchor + neighbour nodes always retain their symbols.
    const collapse = anchored && t === 'context';
    languages[n.language] = (languages[n.language] ?? 0) + 1;
    if (t === 'anchor') anchorCount++;
    else if (t === 'neighbor') neighborCount++;
    else contextCount++;
    return {
      ...n,
      tier: t,
      collapsed: collapse,
      symbol_count: n.symbols.length,
      symbols: collapse ? [] : n.symbols,
    };
  });

  const tokensBefore = map.stats.compressed_tokens_est;
  const body = {
    protocol: 'DELTA_SCP' as const,
    version: map.version,
    status: 'pruned' as const,
    repo: map.repo,
    generated_at: map.generated_at,
    anchor: { paths: anchorPaths, symbols: anchorSymbols },
    languages,
    symbolic_nodes: prunedNodes,
  };
  const tokensAfter = estimateTokens(JSON.stringify(body));
  const focusYield = tokensBefore - tokensAfter;
  const focusRatio =
    tokensBefore > 0 ? Math.round((tokensAfter / tokensBefore) * 10000) / 10000 : 0;

  return {
    ...body,
    stats: {
      anchored,
      anchor_nodes: anchorCount,
      neighbor_nodes: neighborCount,
      context_nodes: contextCount,
      tokens_before: tokensBefore,
      tokens_after: tokensAfter,
      focus_yield: focusYield,
      focus_ratio: focusRatio,
    },
  };
}
