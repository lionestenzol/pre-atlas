// canvas-engine Phase 3 · pipeline orchestrator · URL → live editable React clone

import {
  anatomyV1Schema,
  type AnatomyV1,
  type Region,
} from '../adapter/v1-schema.js';
import { buildClonePreamble } from '../adapter/v1-to-prompt.js';
import {
  buildPatternRegistry,
  pickPattern,
  type Pattern,
} from '../pattern-library/index.js';
import type { VitePool } from '../sandbox/vite-pool.js';
import type { SessionStore } from './session-store.js';

const PATTERN_REGISTRY = buildPatternRegistry();

type Slot = 'header' | 'nav' | 'aside' | 'main' | 'footer';

export type CloneEvent =
  | {
      type: 'status';
      phase: 'resolve' | 'anatomy' | 'adapt' | 'generate' | 'sandbox-ready';
      message: string;
    }
  | { type: 'file'; path: string; content: string }
  | { type: 'preamble'; preview: string }
  | { type: 'done'; sessionId: string; url: string; fileCount: number }
  | { type: 'error'; phase: string; message: string };

export interface UrlToCloneOptions {
  url: string;
  intent?: string;
}

export interface PipelineDeps {
  pool: VitePool;
  resolveCapture: (
    url: string,
  ) => Promise<{ capturePath: string; envelope: AnatomyV1 } | null>;
  store?: SessionStore;
}

interface GeneratedFile {
  path: string;
  content: string;
}

export interface RegionComponentSpec {
  region: Region;
  componentName: string;
  filePath: string;
  pattern: Pattern;
  slot: Slot;
}

const SLOT_BY_PATTERN: Record<string, Slot> = {
  'landmark/header': 'header',
  'landmark/nav': 'nav',
  'landmark/aside': 'aside',
  'landmark/footer': 'footer',
};

function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function toPascalCase(value: string): string {
  const cleaned = value
    .split(/[\s-]+/)
    .map((part) => part.replace(/[^a-zA-Z0-9]/g, ''))
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1));

  const joined = cleaned.join('');
  return /^[0-9]/.test(joined) ? `R${joined}` : joined;
}

function buildRegionComponentSpecs(
  envelope: AnatomyV1,
): RegionComponentSpec[] {
  const seenNames = new Map<string, number>();
  // Each landmark slot can only be filled once · subsequent regions with the
  // same landmark pattern fall back to the main slot so the page stays sane.
  const claimedSlots = new Set<Slot>();

  return [...envelope.regions]
    .sort((left, right) => left.n - right.n)
    .map((region) => {
      const baseName = toPascalCase(region.name) || `Region${region.n}`;
      const duplicateIndex = seenNames.get(baseName) ?? 0;
      seenNames.set(baseName, duplicateIndex + 1);

      const componentName =
        duplicateIndex === 0 ? baseName : `${baseName}${region.n}`;

      const { pattern } = pickPattern(region, PATTERN_REGISTRY);
      const proposedSlot = SLOT_BY_PATTERN[pattern.name] ?? 'main';
      const slot: Slot =
        proposedSlot !== 'main' && !claimedSlots.has(proposedSlot)
          ? proposedSlot
          : 'main';
      if (slot !== 'main') claimedSlots.add(slot);

      return {
        region,
        componentName,
        filePath: `src/components/${componentName}.jsx`,
        pattern,
        slot,
      };
    });
}

interface SlottedSpecs {
  header?: RegionComponentSpec;
  nav?: RegionComponentSpec;
  aside?: RegionComponentSpec;
  footer?: RegionComponentSpec;
  main: RegionComponentSpec[];
}

function groupBySlot(specs: RegionComponentSpec[]): SlottedSpecs {
  const out: SlottedSpecs = { main: [] };
  for (const spec of specs) {
    if (spec.slot === 'main') {
      out.main.push(spec);
      continue;
    }
    out[spec.slot] = spec;
  }
  return out;
}

// MainBlock · post-slotting composition tree for the main column.
// `single`  · one component, rendered inline.
// `cluster` · ≥3 adjacent same-group components, wrapped in a flex row so the
//             clone doesn't degrade to a vertical pile of buttons / pills.
// `section` · a heading region followed by all non-heading specs until the
//             next heading, wrapped in a card so the heading anchors content.
//             Empty heading runs (heading-after-heading-after-heading) collapse
//             to bare singles instead of a row of empty section cards.
export type MainBlock =
  | { kind: 'single'; spec: RegionComponentSpec }
  | { kind: 'cluster'; specs: RegionComponentSpec[] }
  | {
      kind: 'section';
      heading: RegionComponentSpec;
      children: MainBlock[];
    };

const CLUSTER_MIN = 3;
const CLUSTERABLE_GROUPS: ReadonlySet<string> = new Set([
  'clickable',
  'list',
  'card',
]);

function clusterKey(spec: RegionComponentSpec): string | null {
  return CLUSTERABLE_GROUPS.has(spec.pattern.group)
    ? spec.pattern.group
    : null;
}

function groupClusters(specs: RegionComponentSpec[]): MainBlock[] {
  const out: MainBlock[] = [];
  let i = 0;
  while (i < specs.length) {
    const key = clusterKey(specs[i]);
    if (key !== null) {
      let j = i;
      while (j < specs.length && clusterKey(specs[j]) === key) j += 1;
      const run = specs.slice(i, j);
      if (run.length >= CLUSTER_MIN) {
        out.push({ kind: 'cluster', specs: run });
      } else {
        for (const s of run) out.push({ kind: 'single', spec: s });
      }
      i = j;
    } else {
      out.push({ kind: 'single', spec: specs[i] });
      i += 1;
    }
  }
  return out;
}

export function buildMainBlocks(specs: RegionComponentSpec[]): MainBlock[] {
  const blocks: MainBlock[] = [];
  let preHeading: RegionComponentSpec[] = [];
  let current:
    | { heading: RegionComponentSpec; pending: RegionComponentSpec[] }
    | null = null;

  const flushPre = (): void => {
    if (preHeading.length === 0) return;
    for (const b of groupClusters(preHeading)) blocks.push(b);
    preHeading = [];
  };
  const closeSection = (): void => {
    if (current === null) return;
    // No content under this heading · don't wrap in a card. Render the heading
    // as a single block so adjacent headings collapse into a clean list rather
    // than a row of empty section cards.
    if (current.pending.length === 0) {
      blocks.push({ kind: 'single', spec: current.heading });
    } else {
      blocks.push({
        kind: 'section',
        heading: current.heading,
        children: groupClusters(current.pending),
      });
    }
    current = null;
  };

  for (const spec of specs) {
    if (spec.pattern.group === 'heading') {
      if (current === null) flushPre();
      else closeSection();
      current = { heading: spec, pending: [] };
      continue;
    }
    if (current === null) preHeading.push(spec);
    else current.pending.push(spec);
  }
  if (current === null) flushPre();
  else closeSection();
  return blocks;
}

function renderMainBlock(block: MainBlock, indent: string): string {
  switch (block.kind) {
    case 'single':
      return `${indent}<${block.spec.componentName} />`;
    case 'cluster': {
      const lines = [
        `${indent}<div className="flex flex-wrap items-center gap-2">`,
        ...block.specs.map((s) => `${indent}  <${s.componentName} />`),
        `${indent}</div>`,
      ];
      return lines.join('\n');
    }
    case 'section': {
      const lines = [
        `${indent}<section className="flex flex-col gap-3 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">`,
        `${indent}  <${block.heading.componentName} />`,
        ...block.children.map((c) => renderMainBlock(c, `${indent}  `)),
        `${indent}</section>`,
      ];
      return lines.join('\n');
    }
  }
}

function renderApp(specs: RegionComponentSpec[]): string {
  const imports = specs
    .map(
      (spec) =>
        `import ${spec.componentName} from './components/${spec.componentName}.jsx';`,
    )
    .join('\n');
  const slots = groupBySlot(specs);
  const blocks = buildMainBlocks(slots.main);
  const mainBody = blocks
    .map((b) => renderMainBlock(b, '          '))
    .join('\n');

  // Layout shell · landmarks pin to slots, everything else flows through main.
  // Aside, when present, forms a 2-col grid with main; otherwise main is full
  // width. Header / nav / footer are full-width bands above and below.
  const headerLine = slots.header
    ? `      <${slots.header.componentName} />`
    : '';
  const navLine = slots.nav
    ? `      <${slots.nav.componentName} />`
    : '';
  const footerLine = slots.footer
    ? `      <${slots.footer.componentName} />`
    : '';
  const asideLine = slots.aside
    ? `        <${slots.aside.componentName} />`
    : '';
  const mainOuterClass = slots.aside
    ? '"mx-auto grid w-full max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[260px_minmax(0,1fr)]"'
    : '"mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-6"';
  const mainInnerOpen = slots.aside
    ? '        <main className="flex flex-col gap-4 min-w-0">'
    : '        <main className="flex flex-col gap-4">';

  const lines: string[] = [
    imports,
    '',
    'export default function App() {',
    '  return (',
    '    <div className="min-h-screen bg-slate-50 text-slate-900">',
  ];
  if (headerLine) lines.push(headerLine);
  if (navLine) lines.push(navLine);
  lines.push(`      <div className=${mainOuterClass}>`);
  if (asideLine) lines.push(asideLine);
  lines.push(mainInnerOpen);
  if (mainBody) lines.push(mainBody);
  lines.push('        </main>');
  lines.push('      </div>');
  if (footerLine) lines.push(footerLine);
  lines.push('    </div>');
  lines.push('  );');
  lines.push('}');
  return lines.join('\n');
}

function generateFromEnvelope(envelope: AnatomyV1): GeneratedFile[] {
  const specs = buildRegionComponentSpecs(envelope);
  const files: GeneratedFile[] = [
    {
      path: 'src/App.jsx',
      content: renderApp(specs),
    },
    {
      path: 'src/index.css',
      content: ['@tailwind base;', '@tailwind components;', '@tailwind utilities;', ''].join(
        '\n',
      ),
    },
  ];

  for (const spec of specs) {
    files.push({
      path: spec.filePath,
      content: spec.pattern.render({
        componentName: spec.componentName,
        region: spec.region,
        chains: envelope.chains,
      }),
    });
  }

  return files;
}

export async function* runUrlToClone(
  opts: UrlToCloneOptions,
  deps: PipelineDeps,
): AsyncGenerator<CloneEvent> {
  yield {
    type: 'status',
    phase: 'resolve',
    message: `looking up cached capture for ${opts.url}`,
  };

  let resolved: Awaited<ReturnType<PipelineDeps['resolveCapture']>>;
  try {
    resolved = await deps.resolveCapture(opts.url);
  } catch (error) {
    yield {
      type: 'error',
      phase: 'resolve',
      message: formatErrorMessage(error),
    };
    return;
  }

  if (resolved === null) {
    yield {
      type: 'error',
      phase: 'resolve',
      message: `no cached capture found for ${opts.url}`,
    };
    return;
  }

  yield {
    type: 'status',
    phase: 'anatomy',
    message: `envelope loaded · ${resolved.envelope.regions.length} regions ${resolved.envelope.chains.length} chains`,
  };

  let envelope: AnatomyV1;
  try {
    envelope = anatomyV1Schema.parse(resolved.envelope);
  } catch (error) {
    yield {
      type: 'error',
      phase: 'anatomy',
      message: formatErrorMessage(error),
    };
    return;
  }

  yield {
    type: 'status',
    phase: 'adapt',
    message: 'building structural preamble',
  };

  let preamble: string;
  try {
    preamble = buildClonePreamble(envelope, { intent: opts.intent });
  } catch (error) {
    yield {
      type: 'error',
      phase: 'adapt',
      message: formatErrorMessage(error),
    };
    return;
  }

  yield { type: 'preamble', preview: preamble.slice(0, 200) };
  yield {
    type: 'status',
    phase: 'generate',
    message: 'generating React clone (deterministic-from-anatomy stub)',
  };

  let files: GeneratedFile[];
  try {
    files = generateFromEnvelope(envelope);
    // TODO: Phase 3b · when ANTHROPIC_API_KEY is set, replace generateFromEnvelope
    // with the real Anthropic SDK streaming path using the preamble, intent, and
    // open-lovable system prompt via messages.create({ stream: true }).
  } catch (error) {
    yield {
      type: 'error',
      phase: 'generate',
      message: formatErrorMessage(error),
    };
    return;
  }

  let session: Awaited<ReturnType<VitePool['allocate']>>;
  try {
    session = await deps.pool.allocate();
    await deps.pool.writeFiles(session.sessionId, files);
  } catch (error) {
    yield {
      type: 'error',
      phase: 'sandbox-ready',
      message: formatErrorMessage(error),
    };
    return;
  }

  if (deps.store !== undefined) {
    deps.store.registerClone({
      sessionId: session.sessionId,
      envelope,
      capturePath: resolved.capturePath,
      url: session.url,
      rootDir: session.rootDir,
    });
  }

  for (const file of files) {
    yield { type: 'file', path: file.path, content: file.content };
  }

  yield {
    type: 'status',
    phase: 'sandbox-ready',
    message: `vite serving at ${session.url}`,
  };
  yield {
    type: 'done',
    sessionId: session.sessionId,
    url: session.url,
    fileCount: files.length,
  };
}
