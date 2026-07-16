// canvas-engine · IMAGE → 1:1 React, FUSED (deterministic structure + AI look)
//
// The fusion wire of the bidirectional hub. It STACKS the two engines instead of
// picking one:
//   1. extract the AnatomyV1 envelope from the screenshot (structure · the "map")
//   2. run the vision codegen WITH that structure as a scaffold, so the output is
//      pixel-faithful to the screenshot AND organized into the map's components.
//
// The image stays the source of truth for the LOOK; the envelope only fixes the
// component split, names, and order. The clone carries the envelope (so the map
// is retrievable via GET /sessions/:id/envelope) but is marked generator:'llm' —
// the JSX is AI-authored, so its edits use the free-form claude path, not the
// deterministic region loop (which assumes deterministically-emitted components).

import { parseStreamedBlocks } from '../vendor/lovable/parse-blocks.js';
import type { AnatomyV1 } from '../adapter/v1-schema.js';
import { toPascalCase } from './component-names.js';
import type { VitePool } from '../sandbox/vite-pool.js';
import {
  buildVisionInstruction,
  generateCloneCode,
  type ImagePipelineDeps,
  type ImageToCloneOptions,
} from './image-to-clone.js';
import { extractEnvelopeFromImage } from './image-to-envelope.js';
import type { CloneEvent } from './url-to-clone.js';

interface GeneratedFile {
  path: string;
  content: string;
}

function formatErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// Append the envelope's structure to the base vision prompt as a component plan.
// The screenshot remains the source of truth for the look; this only fixes the
// component boundaries, names, and order.
export function buildGuidedInstruction(
  envelope: AnatomyV1,
  intent?: string,
): string {
  const base = buildVisionInstruction(intent);
  const plan = [...envelope.regions]
    .sort((a, b) => a.n - b.n)
    .map((r) => {
      const comp = toPascalCase(r.name) || 'Region';
      const desc = r.desc !== undefined ? ` — ${r.desc}` : '';
      const where =
        r.bounds !== undefined
          ? `  [~${Math.round(r.bounds.x)},${Math.round(r.bounds.y)} ${Math.round(r.bounds.w)}x${Math.round(r.bounds.h)}%]`
          : '';
      return `${r.n}. ${comp}${desc}${where}`;
    })
    .join('\n');

  return `${base}

## Component plan (from the structure map)
Organize the UI into these components, one file each under src/components/, default-exported, and compose them in src/App.jsx to match the screenshot's layout and order:

${plan}

Use this plan only to decide component boundaries, names, and order. Match the screenshot's pixels, text, colors, and spacing exactly.`;
}

export async function* runImageToCloneGuided(
  opts: ImageToCloneOptions,
  deps: ImagePipelineDeps,
): AsyncGenerator<CloneEvent> {
  yield {
    type: 'status',
    phase: 'anatomy',
    message: 'extracting UI structure from screenshot',
  };

  let envelope: AnatomyV1;
  try {
    envelope = await extractEnvelopeFromImage(opts.image, {
      intent: opts.intent,
      apiKey: deps.apiKey,
    });
  } catch (error) {
    yield { type: 'error', phase: 'anatomy', message: formatErrorMessage(error) };
    return;
  }

  yield {
    type: 'status',
    phase: 'adapt',
    message: `structure map · ${envelope.regions.length} regions · guiding vision codegen`,
  };

  const instruction = buildGuidedInstruction(envelope, opts.intent);
  yield { type: 'preamble', preview: instruction.slice(0, 200) };
  yield {
    type: 'status',
    phase: 'generate',
    message: 'generating 1:1 React (vision, structure-guided)',
  };

  let rawText: string;
  try {
    rawText = await generateCloneCode(opts.image, instruction, deps.apiKey);
  } catch (error) {
    yield { type: 'error', phase: 'generate', message: formatErrorMessage(error) };
    return;
  }

  const { files } = parseStreamedBlocks(rawText);
  const generated: GeneratedFile[] = files.filter((f) => f.content.length > 0);
  if (!generated.some((f) => f.path === 'src/App.jsx')) {
    yield {
      type: 'error',
      phase: 'generate',
      message: 'model did not return a src/App.jsx file block',
    };
    return;
  }

  let session: Awaited<ReturnType<VitePool['allocate']>>;
  try {
    session = await deps.pool.allocate();
  } catch (error) {
    yield {
      type: 'error',
      phase: 'sandbox-ready',
      message: formatErrorMessage(error),
    };
    return;
  }

  try {
    await deps.pool.writeFiles(session.sessionId, generated);
  } catch (error) {
    try {
      await deps.pool.release(session.sessionId);
    } catch {
      // best-effort cleanup
    }
    yield {
      type: 'error',
      phase: 'sandbox-ready',
      message: formatErrorMessage(error),
    };
    return;
  }

  // Carries the envelope (the map is retrievable) but generator:'llm' · the JSX
  // is AI-authored, so edits use the free-form claude path.
  deps.store?.registerClone({
    sessionId: session.sessionId,
    source: 'image',
    generator: 'llm',
    envelope,
    url: session.url,
    rootDir: session.rootDir,
  });

  for (const file of generated) {
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
    fileCount: generated.length,
  };
}
