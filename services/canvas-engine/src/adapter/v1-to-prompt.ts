// canvas-engine Phase 2 · clone-mode adapter · consumes anatomy-v1 envelope

import {
  anatomyV1Schema,
  type AnatomyV1,
  type Bounds,
  type Chain,
  type ChainNode,
  type Fetch,
  type Region,
} from './v1-schema.js';

export interface BuildClonePreambleOptions {
  intent?: string;
}

function formatBounds(bounds: Bounds): string {
  return `x=${bounds.x} y=${bounds.y} w=${bounds.w} h=${bounds.h}`;
}

function formatSource(file?: string, line?: number): string | null {
  if (!file) {
    return null;
  }

  return line === undefined ? file : `${file}:${line}`;
}

function formatFetch(fetch: Fetch): string {
  const metaParts: string[] = [];

  if (fetch.status !== undefined) {
    metaParts.push(String(fetch.status));
  }

  if (fetch.contentType) {
    metaParts.push(fetch.contentType);
  }

  if (metaParts.length === 0) {
    return `     · ${fetch.method} ${fetch.url}`;
  }

  return `     · ${fetch.method} ${fetch.url} (${metaParts.join(' ')})`;
}

function formatRegion(region: Region, index: number): string[] {
  const lines: string[] = [
    `${index}. **${region.name}** (id=${region.id}, n=${region.n}, layer=${region.layer})`,
  ];

  if (region.selector) {
    lines.push(`   - Selector: \`${region.selector}\``);
  }

  if (region.bounds) {
    lines.push(`   - Bounds: ${formatBounds(region.bounds)}`);
  }

  const source = formatSource(region.file, region.line);
  if (source) {
    lines.push(`   - Source: ${source}`);
  }

  if (region.detection) {
    lines.push(`   - Detection: ${region.detection}`);
  }

  if (region.desc) {
    lines.push(`   - Notes: ${region.desc}`);
  }

  if (region.fetches && region.fetches.length > 0) {
    lines.push('   - Fetches:');
    for (const fetch of region.fetches) {
      lines.push(formatFetch(fetch));
    }
  }

  return lines;
}

function formatChainNode(node: ChainNode): string {
  const parts = [`   - n${node.n} [${node.layer}] ${node.label}`];

  if (node.detail) {
    parts.push(` · ${node.detail}`);
  }

  const source = formatSource(node.file, node.line);
  if (source) {
    parts.push(` (${source})`);
  }

  return parts.join('');
}

function formatChain(chain: Chain, index: number): string[] {
  const lines: string[] = [`${index}. **${chain.id}**`];

  for (const node of chain.nodes) {
    lines.push(formatChainNode(node));
  }

  return lines;
}

export function buildClonePreamble(
  envelope: AnatomyV1,
  opts?: BuildClonePreambleOptions,
): string {
  const lines: string[] = [];
  const regionCount = envelope.regions.length;
  const chainCount = envelope.chains.length;

  lines.push('## Captured structure (anatomy-v1)');
  lines.push('');
  lines.push(
    `Source: ${envelope.metadata.target} · captured ${envelope.metadata.timestamp} via ${envelope.metadata.tools.join(', ')}`,
  );
  lines.push(
    `${regionCount} regions and ${chainCount} backend chain(s) detected. Use these to inform layout, copy, fetch calls, and behavior.`,
  );
  lines.push('');
  lines.push(`### Regions (${regionCount})`);
  lines.push('');

  envelope.regions.forEach((region, index) => {
    if (index > 0) {
      lines.push('');
    }

    lines.push(...formatRegion(region, index + 1));
  });

  if (chainCount > 0) {
    lines.push('');
    lines.push(`### Backend chains (${chainCount})`);
    lines.push('');

    envelope.chains.forEach((chain, index) => {
      if (index > 0) {
        lines.push('');
      }

      lines.push(...formatChain(chain, index + 1));
    });
  }

  lines.push('');
  lines.push('### Generation directives');
  lines.push('');
  lines.push(
    '- Use the bounds above to inform CSS layout (Tailwind utility classes). Approximate, don\'t pixel-match.',
  );
  lines.push(
    '- For every fetch URL listed above, emit a real fetch call in the generated React code. Do not invent endpoints.',
  );
  lines.push(
    '- For every chain that ends in an `api` or `ext` node, the generated client code MUST hit the api node\'s URL.',
  );
  lines.push(
    "- Region names are component name suggestions. Don't rename them unless intent says so.",
  );

  if (opts?.intent) {
    lines.push(`- Intent: ${opts.intent}`);
  }

  return lines.join('\n').trimEnd();
}

export function parseAndBuildClonePreamble(
  rawJson: unknown,
  opts?: BuildClonePreambleOptions,
): string {
  const envelope = anatomyV1Schema.parse(rawJson);
  return buildClonePreamble(envelope, opts);
}
