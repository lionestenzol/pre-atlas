// Delta SCP · the flue — routing handoff to the Chainer / Drop List
//
// The engine's native output is JSON. The Chainer (droplist) consumes dense
// Markdown drops. The flue renders a compressed/pruned map as a compact Markdown
// payload and hands it off.
//
// Handoff is file-inbox by default: write the payload as a .md drop into a
// watched directory. droplist already works on a drop -> packet -> DAG grain, so
// a dropped file fits its model with zero edits to droplist's code, and the two
// services stay loosely coupled across their separate repo roots. An HTTP POST
// target can be layered on later without touching the renderer.
//
// renderFlueMarkdown is pure (no I/O); emitToFlue is the thin filesystem wrapper.

import { mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import type { CompressedState } from './compressor.js';
import type { PrunedState, PrunedNode } from './prune.js';

type AnyMap = CompressedState | PrunedState;

function isPruned(map: AnyMap): map is PrunedState {
  return map.status === 'pruned';
}

function tierBadge(node: PrunedNode): string {
  if (node.collapsed) return '·'; // stub
  return node.tier === 'anchor' ? '◆' : node.tier === 'neighbor' ? '◇' : '○';
}

function renderSymbols(symbols: { kind: string; name: string; line: number }[]): string {
  if (symbols.length === 0) return '';
  return symbols.map((s) => `\`${s.kind} ${s.name}\` (L${s.line})`).join(', ');
}

/**
 * Render a Delta SCP map as a dense Markdown drop for the Chainer.
 *
 * Pruned maps render focus-first: anchors, then neighbours, then a single
 * collapsed line listing the stubbed context files (path + symbol count) so the
 * Chainer can see what exists without paying for its symbols.
 */
export function renderFlueMarkdown(map: AnyMap): string {
  const lines: string[] = [];
  const pruned = isPruned(map);

  lines.push(`# Delta SCP ${pruned ? 'focus' : 'map'} · ${map.repo}`);
  lines.push('');
  lines.push(`- protocol: \`${map.protocol}\` v${map.version}`);
  lines.push(`- generated: ${map.generated_at}`);

  if (pruned) {
    const s = map.stats;
    lines.push(`- anchored: **${s.anchored}** · anchor ${s.anchor_nodes} · neighbor ${s.neighbor_nodes} · context ${s.context_nodes}`);
    lines.push(`- focus: ${s.tokens_before} -> ${s.tokens_after} tok (yield ${s.focus_yield}, ratio ${s.focus_ratio})`);
    if (map.anchor.paths.length) lines.push(`- anchor paths: ${map.anchor.paths.map((p) => `\`${p}\``).join(', ')}`);
    if (map.anchor.symbols.length) lines.push(`- anchor symbols: ${map.anchor.symbols.map((p) => `\`${p}\``).join(', ')}`);
  } else {
    const s = map.stats;
    lines.push(`- files: ${s.files_included} · raw ${s.raw_tokens_est} tok -> compressed ${s.compressed_tokens_est} tok (yield ${s.token_yield}, ratio ${s.compression_ratio})`);
  }
  lines.push('');

  if (pruned) {
    const nodes = map.symbolic_nodes;
    const detailed = nodes.filter((n) => !n.collapsed);
    const stubbed = nodes.filter((n) => n.collapsed);

    lines.push('## Focus');
    for (const n of detailed) {
      lines.push(`### ${tierBadge(n)} ${n.path} _(${n.tier}, ${n.language})_`);
      const sym = renderSymbols(n.symbols);
      lines.push(sym ? sym : '_(no symbols)_');
      lines.push('');
    }
    if (stubbed.length) {
      lines.push('## Context (collapsed)');
      lines.push(
        stubbed
          .map((n) => `- \`${n.path}\` (${n.language}, ${n.symbol_count} sym)`)
          .join('\n'),
      );
      lines.push('');
    }
  } else {
    lines.push('## Files');
    for (const n of map.symbolic_nodes) {
      lines.push(`### ${n.path} _(${n.language})_`);
      const sym = renderSymbols(n.symbols);
      lines.push(sym ? sym : '_(no symbols)_');
      lines.push('');
    }
  }

  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

// A stable, collision-resistant drop filename from repo + content. Deterministic
// for identical payloads (so re-emitting the same map overwrites rather than
// piling up duplicate drops).
function dropFilename(map: AnyMap, markdown: string): string {
  const slugRepo = map.repo.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48) || 'repo';
  const hash = createHash('sha256').update(markdown).digest('hex').slice(0, 12);
  return `delta-scp-${slugRepo}-${hash}.md`;
}

export interface FlueResult {
  path: string;
  bytes: number;
  filename: string;
}

/**
 * Write the Markdown payload into the flue inbox directory. Returns where it
 * landed. Idempotent for identical payloads (content-hashed filename).
 */
export async function emitToFlue(
  markdown: string,
  map: AnyMap,
  inboxDir: string,
): Promise<FlueResult> {
  const dir = path.resolve(inboxDir);
  await mkdir(dir, { recursive: true });
  const filename = dropFilename(map, markdown);
  const dest = path.join(dir, filename);
  await writeFile(dest, markdown, 'utf8');
  return { path: dest, bytes: Buffer.byteLength(markdown, 'utf8'), filename };
}
