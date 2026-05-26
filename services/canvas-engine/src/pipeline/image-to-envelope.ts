// canvas-engine · IMAGE → AnatomyV1 envelope (the LLM structure bridge)
//
// The keystone of the bidirectional hub. A screenshot is the ONE representation
// that can't reach the AnatomyV1 envelope deterministically: there's no DOM to
// walk (extension) and no source to parse (url/anatomy static trace). This module
// is the LLM bridge that crosses the pixel→structure gap. Once a screenshot
// becomes a validated envelope it plugs into the SAME deterministic consumers the
// url/anatomy path already uses:
//
//     IMAGE ──(LLM, here)──▶ ENVELOPE ──(generateFromEnvelope, deterministic)──▶ React
//
// Contrast with the vision path (image-to-clone.ts), which is the diagonal
// shortcut IMAGE──(LLM)──▶CODE that skips the hub: it produces pixels-as-code with
// no structure object, so it can't round-trip or join the deterministic edit-loop.
// The clone produced here DOES carry an envelope, so it joins that edit-loop.
//
// Backend (CLI subscription vs SDK key) is chosen by the shared vision-backend
// selector, identical to image-to-clone.ts.

import { rm } from 'node:fs/promises';
import path from 'node:path';

import Anthropic from '@anthropic-ai/sdk';
import { z } from 'zod';

import {
  anatomyV1Schema,
  type AnatomyV1,
  type Bounds,
  type Layer,
  type Region,
} from '../adapter/v1-schema.js';
import type { VitePool } from '../sandbox/vite-pool.js';
import { runClaudeCli } from './claude-cli.js';
import { resolveVisionBackend } from './vision-backend.js';
import {
  buildImageBlock,
  writeTempImage,
  type ImagePipelineDeps,
  type ImageToCloneOptions,
} from './image-to-clone.js';
import { generateFromEnvelope, type CloneEvent } from './url-to-clone.js';
import { readPngSize } from './asset-extract.js';

const DEFAULT_VISION_MODEL =
  process.env.CANVAS_ENGINE_VISION_MODEL ?? 'claude-sonnet-4-6';
const MAX_OUTPUT_TOKENS = 8000;

// "role" is the small, intuitive vocabulary the model emits per region. We map
// each role to the detection/kind tokens that normalizeDetection() recognises,
// so the synthesised envelope routes through pickPattern to a real pattern group
// rather than collapsing to "default". (See pattern-library/normalize.ts — this
// table is the image-side mirror of that contract.)
type RegionRole =
  | 'header'
  | 'nav'
  | 'sidebar'
  | 'footer'
  | 'section'
  | 'heading'
  | 'button'
  | 'link'
  | 'cta'
  | 'form'
  | 'input'
  | 'list'
  | 'card'
  | 'image'
  | 'logo'
  | 'icon'
  | 'text';

const ROLE_TO_DETECTION: Record<RegionRole, { detection: string; kind?: string }> = {
  header: { detection: 'sem-header' },
  nav: { detection: 'sem-nav' },
  sidebar: { detection: 'sem-aside' },
  footer: { detection: 'sem-footer' },
  section: { detection: 'sem-section' },
  heading: { detection: 'heading' },
  button: { detection: 'r7-native-interactive', kind: 'click' },
  link: { detection: 'r7-native-interactive', kind: 'click' },
  cta: { detection: 'hero', kind: 'click' },
  form: { detection: 'form' },
  input: { detection: 'form' },
  list: { detection: 'pattern-repeat', kind: 'list' },
  card: { detection: 'card-heuristic', kind: 'card' },
  // image / logo / icon → kind:'image' so the deterministic generator slices the
  // real pixels out of the screenshot (asset-extract.ts) instead of a placeholder.
  image: { detection: 'default', kind: 'image' },
  logo: { detection: 'default', kind: 'image' },
  icon: { detection: 'default', kind: 'image' },
  text: { detection: 'default' },
};

const ROLES = Object.keys(ROLE_TO_DETECTION) as RegionRole[];

// Canonical layer palette · shared visual language with the anatomy-map skill.
// Only used for rendering/annotation, never codegen, but the schema requires all
// five keys present.
const LAYERS: Record<Layer, { color: string }> = {
  ui: { color: '#c084fc' },
  api: { color: '#f59e0b' },
  lib: { color: '#22c55e' },
  ext: { color: '#818cf8' },
  state: { color: '#a855f7' },
};

const llmRegionSchema = z.object({
  name: z.string().min(1),
  role: z.string().min(1),
  desc: z.string().optional(),
  x: z.number().optional(),
  y: z.number().optional(),
  w: z.number().optional(),
  h: z.number().optional(),
});

const llmOutputSchema = z.object({
  regions: z.array(llmRegionSchema).min(1),
});

const EXTRACTOR_SYSTEM = `You are a UI structure extractor. You are shown a single screenshot of a web or app UI. Identify the distinct, meaningful UI regions and describe them as structured data.

Output ONLY a single JSON object. No prose, no markdown code fences. Shape:
{"regions":[{"name":"...","role":"...","desc":"...","x":0,"y":0,"w":0,"h":0}]}

Field rules:
- name: 2 to 4 word human label (e.g. "Primary nav", "Hero heading", "Sign-up form").
- role: EXACTLY one of: ${ROLES.join(', ')}.
- desc: one short sentence on the region's purpose.
- x, y, w, h: bounding box as PERCENTAGES of the image, 0 to 100. x,y = top-left corner; w,h = width and height.
- Emit 8 to 24 regions. Prefer salient top-level regions over tiny details.
- role guidance: header/nav/sidebar/footer/section for layout landmarks; heading for titles; button/link/cta for clickable controls; form/input for inputs; list for repeated item groups; card for bordered content blocks; image for photos/illustrations, logo for brand marks, icon for small glyphs; text for paragraphs.
- ALWAYS give x/y/w/h for every image, logo, and icon · those bounds are used to slice the real pixels out of the screenshot.
- Do NOT invent backend, API, or network details. You cannot see them in a screenshot.`;

const EXTRACTOR_USER = 'Extract the UI regions now and output the JSON object.';

function formatErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function slugify(value: string): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug.length > 0 ? slug : 'region';
}

function normalizeRole(role: string): RegionRole {
  const lower = role.trim().toLowerCase();
  return (ROLES as string[]).includes(lower) ? (lower as RegionRole) : 'text';
}

// The model occasionally wraps JSON in prose or a ```json fence despite the
// instruction. Pull the outermost {...} object out before parsing.
function extractJsonObject(raw: string): unknown {
  const fenced = /```(?:json)?\s*([\s\S]*?)```/i.exec(raw);
  const candidate = fenced !== null ? fenced[1] : raw;
  const start = candidate.indexOf('{');
  const end = candidate.lastIndexOf('}');
  if (start === -1 || end === -1 || end < start) {
    throw new Error('model did not return a JSON object');
  }
  return JSON.parse(candidate.slice(start, end + 1));
}

function toBounds(r: z.infer<typeof llmRegionSchema>): Bounds | undefined {
  if (
    r.x === undefined ||
    r.y === undefined ||
    r.w === undefined ||
    r.h === undefined
  ) {
    return undefined;
  }
  return { x: r.x, y: r.y, w: r.w, h: r.h };
}

function buildEnvelope(
  rawText: string,
  target: string,
  backend: string,
): AnatomyV1 {
  const parsed = llmOutputSchema.parse(extractJsonObject(rawText));

  const regions: Region[] = parsed.regions.map((r, i) => {
    const n = i + 1;
    const role = normalizeRole(r.role);
    const { detection, kind } = ROLE_TO_DETECTION[role];
    const bounds = toBounds(r);
    return {
      id: `${slugify(r.name)}-${n}`,
      n,
      name: r.name,
      layer: 'ui' as const, // a screenshot only exposes the UI layer
      detection,
      ...(kind !== undefined ? { kind } : {}),
      ...(r.desc !== undefined ? { desc: r.desc } : {}),
      ...(bounds !== undefined ? { bounds } : {}),
    };
  });

  const envelope: AnatomyV1 = {
    version: 'anatomy-v1',
    metadata: {
      target,
      mode: 'spa',
      source: 'image',
      timestamp: new Date().toISOString(),
      tools: ['canvas-engine/image-to-envelope', `backend:${backend}`],
    },
    regions,
    chains: [], // backend chains are not observable from a screenshot
    layers: LAYERS,
  };

  // Fail loud if the synthesised envelope drifts from the contract.
  return anatomyV1Schema.parse(envelope);
}

async function streamEnvelopeCompletion(
  apiKey: string,
  imageBlock: Anthropic.ImageBlockParam,
): Promise<string> {
  const client = new Anthropic({ apiKey });
  const stream = client.messages.stream({
    model: DEFAULT_VISION_MODEL,
    max_tokens: MAX_OUTPUT_TOKENS,
    system: EXTRACTOR_SYSTEM,
    messages: [
      {
        role: 'user',
        content: [imageBlock, { type: 'text', text: EXTRACTOR_USER }],
      },
    ],
  });

  let assembled = '';
  for await (const event of stream) {
    if (
      event.type === 'content_block_delta' &&
      event.delta.type === 'text_delta'
    ) {
      assembled += event.delta.text;
    }
  }
  await stream.finalMessage();
  return assembled;
}

// Backend chosen by CANVAS_ENGINE_VISION_BACKEND (see vision-backend.ts):
//   - 'sdk'  → Anthropic API directly (requires a key)
//   - 'cli'  → claude CLI only, no fallback
//   - 'auto' → claude CLI first (no key), SDK fallback if the CLI fails and a key
//              is configured. (default)
async function generateEnvelopeText(
  image: string,
  apiKey?: string,
): Promise<string> {
  const backend = resolveVisionBackend();

  if (backend === 'sdk') {
    if (apiKey === undefined || apiKey.length === 0) {
      throw new Error(
        'CANVAS_ENGINE_VISION_BACKEND=sdk requires ANTHROPIC_API_KEY to be set',
      );
    }
    return await streamEnvelopeCompletion(apiKey, buildImageBlock(image));
  }

  let tmpPath: string | undefined;
  try {
    tmpPath = await writeTempImage(image);
    const prompt = `Read the screenshot at: ${tmpPath}\n\n${EXTRACTOR_USER}`;
    return await runClaudeCli({
      system: EXTRACTOR_SYSTEM,
      prompt,
      imagePath: tmpPath,
    });
  } catch (cliError) {
    if (backend === 'auto' && apiKey !== undefined && apiKey.length > 0) {
      return await streamEnvelopeCompletion(apiKey, buildImageBlock(image));
    }
    throw new Error(
      backend === 'cli'
        ? `claude CLI structure extraction failed (CANVAS_ENGINE_VISION_BACKEND=cli, no SDK fallback): ${formatErrorMessage(cliError)}`
        : `claude CLI structure extraction failed and no ANTHROPIC_API_KEY fallback is set: ${formatErrorMessage(cliError)}`,
    );
  } finally {
    if (tmpPath !== undefined) {
      await rm(path.dirname(tmpPath), { recursive: true, force: true }).catch(
        () => undefined,
      );
    }
  }
}

// Screenshot → validated AnatomyV1 envelope. Exported so the fused path
// (image-to-clone-guided.ts) can extract the structure before guiding codegen.
export async function extractEnvelopeFromImage(
  image: string,
  opts?: { intent?: string; apiKey?: string },
): Promise<AnatomyV1> {
  const backend = resolveVisionBackend();
  const target =
    opts?.intent !== undefined && opts.intent.trim().length > 0
      ? opts.intent.trim().slice(0, 120)
      : 'screenshot';
  const rawText = await generateEnvelopeText(image, opts?.apiKey);
  return buildEnvelope(rawText, target, backend);
}

export async function* runImageToEnvelope(
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
    phase: 'anatomy',
    message: `envelope · ${envelope.regions.length} regions ${envelope.chains.length} chains`,
  };
  yield {
    type: 'preamble',
    preview: envelope.regions
      .slice(0, 8)
      .map((r) => r.name)
      .join(' · ')
      .slice(0, 200),
  };
  yield {
    type: 'status',
    phase: 'generate',
    message: 'generating React skeleton (deterministic-from-anatomy)',
  };

  let files: ReturnType<typeof generateFromEnvelope>;
  try {
    files = generateFromEnvelope(envelope, {
      imageSrc: opts.image,
      imageSize: readPngSize(opts.image),
    });
  } catch (error) {
    yield { type: 'error', phase: 'generate', message: formatErrorMessage(error) };
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
    await deps.pool.writeFiles(session.sessionId, files);
  } catch (error) {
    // Allocation succeeded; release so the Vite server / port / session dir don't
    // leak if seeding fails.
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

  // Register WITH the envelope. Unlike a vision clone, this image clone carries
  // structure, so it joins the deterministic region edit-loop (see server /edit,
  // which branches on envelope presence).
  deps.store?.registerClone({
    sessionId: session.sessionId,
    source: 'image',
    envelope,
    url: session.url,
    rootDir: session.rootDir,
  });

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

// Offline test surface · lets image-to-envelope.test.ts exercise the
// deterministic transform (model-output string → validated envelope → pattern
// routing) without a live LLM call.
export const __test = {
  buildEnvelope,
  normalizeRole,
  extractJsonObject,
  slugify,
  ROLE_TO_DETECTION,
};
