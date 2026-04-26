// canvas-engine Phase 2 · edit-mode adapter · pinpoint region/chain edits via id

import {
  anatomyV1Schema,
  type AnatomyV1,
  type Chain,
  type Region,
} from './v1-schema.js';

export type EditTarget =
  | { kind: 'region'; region: Region }
  | { kind: 'chain'; chain: Chain }
  | { kind: 'unresolved'; id: string };

export interface BuildEditPromptOptions {
  intent: string;
  id: string;
}

function normalizeEnvelope(envelope: AnatomyV1): AnatomyV1 {
  const parsed = anatomyV1Schema.safeParse(envelope);
  return parsed.success ? parsed.data : envelope;
}

function formatSource(file?: string, line?: number): string | null {
  if (!file) {
    return null;
  }

  return line === undefined ? file : `${file}:${line}`;
}

export function resolveEditTarget(envelope: AnatomyV1, id: string): EditTarget {
  const normalized = normalizeEnvelope(envelope);
  const region = normalized.regions.find((entry) => entry.id === id);

  if (region) {
    return { kind: 'region', region };
  }

  const chain = normalized.chains.find((entry) => entry.id === id);

  if (chain) {
    return { kind: 'chain', chain };
  }

  return { kind: 'unresolved', id };
}

function buildRegionPrompt(region: Region, intent: string): string {
  const lines: string[] = [
    '## Targeted edit (anatomy-v1 · region)',
    '',
    `Target region: **${region.name}** (id=${region.id}, n=${region.n})`,
  ];

  if (region.selector) {
    lines.push(`- Selector: \`${region.selector}\``);
  }

  const source = formatSource(region.file, region.line);
  if (source) {
    lines.push(`- Source: ${source}`);
  }

  if (region.bounds) {
    lines.push(
      `- Bounds: x=${region.bounds.x} y=${region.bounds.y} w=${region.bounds.w} h=${region.bounds.h}`,
    );
  }

  if (region.desc) {
    lines.push(`- Notes: ${region.desc}`);
  }

  if (region.fetches && region.fetches.length > 0) {
    lines.push('- Fetches:');
    for (const fetch of region.fetches) {
      lines.push(`  · ${fetch.method} ${fetch.url}`);
    }
  }

  lines.push('');
  lines.push(`User intent: ${intent}`);
  lines.push('');
  lines.push('### Edit directives');
  lines.push('- ONLY edit files related to the region above. Do not touch other regions.');
  lines.push(
    '- If the region has a `Source` line, that is the file most likely to need editing.',
  );
  lines.push(
    '- Preserve the region\'s existing fetch calls unless intent explicitly changes them.',
  );
  lines.push('- Do not regenerate App.jsx unless the region is the root.');

  return lines.join('\n');
}

function formatChainNode(node: Chain['nodes'][number]): string {
  const detail = node.detail ? ` · ${node.detail}` : '';
  const source = formatSource(node.file, node.line);
  const sourceSuffix = source ? ` (${source})` : '';
  return `- n${node.n} [${node.layer}] ${node.label}${detail}${sourceSuffix}`;
}

function buildChainPrompt(chain: Chain, intent: string): string {
  const lines: string[] = [
    '## Targeted edit (anatomy-v1 · chain)',
    '',
    `Target chain: **${chain.id}**`,
    'Nodes:',
  ];

  for (const node of chain.nodes) {
    lines.push(formatChainNode(node));
  }

  lines.push('');
  lines.push(`User intent: ${intent}`);
  lines.push('');
  lines.push('### Edit directives');
  lines.push('- This is a backend-chain edit. The change spans the listed nodes.');
  lines.push('- For each node with a Source file, edits should land in that file.');
  lines.push(
    '- Preserve the API contract (URL paths, methods) unless intent explicitly changes them.',
  );
  lines.push('- Do not touch UI regions unrelated to this chain.');

  return lines.join('\n');
}

function buildUnresolvedPrompt(id: string, intent: string): string {
  return [
    '## Targeted edit (anatomy-v1 · UNRESOLVED)',
    '',
    `Target id "${id}" was not found in regions[] or chains[]. The editor cannot proceed deterministically.`,
    '',
    `User intent: ${intent}`,
    '',
    '### Edit directives',
    '- Treat this as an unscoped edit. Refuse to make changes and emit a status block explaining the id was not found.',
    '- Suggest similar ids from the envelope if any are close (use Levenshtein in the LLM, do not compute here).',
  ].join('\n');
}

export function buildEditPrompt(
  envelope: AnatomyV1,
  opts: BuildEditPromptOptions,
): string {
  const target = resolveEditTarget(envelope, opts.id);

  if (target.kind === 'region') {
    return buildRegionPrompt(target.region, opts.intent);
  }

  if (target.kind === 'chain') {
    return buildChainPrompt(target.chain, opts.intent);
  }

  return buildUnresolvedPrompt(target.id, opts.intent);
}
