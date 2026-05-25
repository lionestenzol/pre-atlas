// canvas-engine Phase 3 · image → live editable React clone (LLM vision path)
//
// Sibling to url-to-clone.ts. Same CloneEvent contract and same Vite-sandbox
// finalize, but the input is a static screenshot and the generator is a real
// Claude vision call rather than the deterministic anatomy stub. It ports the
// replication prompt from abi/screenshot-to-code (prompts/create/image.py) onto
// open-lovable's React <file>-block output format, so both clone paths converge
// on identical GeneratedFile[] written into the Vite pool.

import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import Anthropic from '@anthropic-ai/sdk';

import { parseStreamedBlocks } from '../vendor/lovable/parse-blocks.js';
import { buildSystemPrompt } from '../vendor/lovable/system-prompt.js';
import type { VitePool } from '../sandbox/vite-pool.js';
import { runClaudeCli } from './claude-cli.js';
import { resolveVisionBackend } from './vision-backend.js';
import type { SessionStore } from './session-store.js';
import type { CloneEvent } from './url-to-clone.js';

const DEFAULT_VISION_MODEL =
  process.env.CANVAS_ENGINE_VISION_MODEL ?? 'claude-sonnet-4-6';
const MAX_OUTPUT_TOKENS = 16000;

type Base64MediaType = 'image/png' | 'image/jpeg' | 'image/gif' | 'image/webp';

const SUPPORTED_MEDIA_TYPES: ReadonlySet<string> = new Set<Base64MediaType>([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
]);

export interface ImageToCloneOptions {
  /** A `data:image/...;base64,...` URL or an `http(s)://` image URL. */
  image: string;
  intent?: string;
}

export interface ImagePipelineDeps {
  pool: VitePool;
  /** Optional SDK fallback key. The CLI backend (default) needs no key. */
  apiKey?: string;
  store?: SessionStore;
}

interface GeneratedFile {
  path: string;
  content: string;
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function buildImageBlock(image: string): Anthropic.ImageBlockParam {
  const dataUrlMatch = /^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/s.exec(image);
  if (dataUrlMatch !== null) {
    const mediaType = dataUrlMatch[1];
    const data = dataUrlMatch[2];
    if (!SUPPORTED_MEDIA_TYPES.has(mediaType)) {
      throw new Error(`unsupported image media type: ${mediaType}`);
    }
    return {
      type: 'image',
      source: {
        type: 'base64',
        media_type: mediaType as Base64MediaType,
        data,
      },
    };
  }

  if (/^https?:\/\//.test(image)) {
    return { type: 'image', source: { type: 'url', url: image } };
  }

  throw new Error('image must be a data: URL (base64) or an http(s) URL');
}

function buildVisionInstruction(intent?: string): string {
  // Ported from abi/screenshot-to-code prompts/create/image.py, retargeted from
  // a single index.html to open-lovable's React + Vite <file>-block output. The
  // output format itself is governed by the system prompt (buildSystemPrompt).
  const base = `Generate a React + Tailwind app (for a Vite project) that looks exactly like the provided screenshot.

## Replication instructions
- Make the app look exactly like the screenshot.
- Use the exact text from the screenshot.
- Match layout, spacing, colors, fonts, and visual hierarchy as closely as possible.
- Do not invent features or content that are not visible in the screenshot.
- For images/logos you cannot reproduce, use a neutral placeholder (https://placehold.co) or a Tailwind-styled box.

## Output
- Output React files using the <file path="..."></file> format from the system prompt.
- The entry component MUST be src/App.jsx with a default export.
- Split obvious sections (header, hero, footer, etc.) into components under src/components/.`;

  if (intent !== undefined && intent.trim().length > 0) {
    return `${base}\n\n## Additional instructions\n${intent.trim()}`;
  }
  return base;
}

async function streamVisionCompletion(
  apiKey: string,
  imageBlock: Anthropic.ImageBlockParam,
  instruction: string,
): Promise<string> {
  const client = new Anthropic({ apiKey });
  const messages: Anthropic.MessageParam[] = [
    {
      role: 'user',
      content: [imageBlock, { type: 'text', text: instruction }],
    },
  ];

  const stream = client.messages.stream({
    model: DEFAULT_VISION_MODEL,
    max_tokens: MAX_OUTPUT_TOKENS,
    system: buildSystemPrompt({ isEdit: false }),
    messages,
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

async function writeTempImage(image: string): Promise<string> {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'canvas-clone-'));

  const dataUrlMatch = /^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/s.exec(image);
  if (dataUrlMatch !== null) {
    const mediaType = dataUrlMatch[1];
    if (!SUPPORTED_MEDIA_TYPES.has(mediaType)) {
      throw new Error(`unsupported image media type: ${mediaType}`);
    }
    const ext = mediaType.split('/')[1].replace('jpeg', 'jpg');
    const file = path.join(dir, `screenshot.${ext}`);
    await writeFile(file, Buffer.from(dataUrlMatch[2], 'base64'));
    return file;
  }

  if (/^https?:\/\//.test(image)) {
    const res = await fetch(image);
    if (!res.ok) {
      throw new Error(`failed to fetch image URL: HTTP ${res.status}`);
    }
    const mediaType = (res.headers.get('content-type') ?? 'image/png')
      .split(';')[0]
      .trim();
    if (!SUPPORTED_MEDIA_TYPES.has(mediaType)) {
      throw new Error(`unsupported image content-type: ${mediaType}`);
    }
    const ext = mediaType.split('/')[1].replace('jpeg', 'jpg');
    const file = path.join(dir, `screenshot.${ext}`);
    await writeFile(file, Buffer.from(await res.arrayBuffer()));
    return file;
  }

  throw new Error('image must be a data: URL (base64) or an http(s) URL');
}

// Generate the clone. Backend chosen by CANVAS_ENGINE_VISION_BACKEND:
//   - 'sdk'  → call the Anthropic API directly (requires a key)
//   - 'cli'  → claude CLI only, no fallback
//   - 'auto' → claude CLI first (no key), SDK fallback if the CLI fails and a
//              key is configured. (default)
async function generateCloneCode(
  image: string,
  instruction: string,
  apiKey?: string,
): Promise<string> {
  const backend = resolveVisionBackend();

  // sdk: skip the CLI entirely and use the key. Best when the CLI can't
  // authenticate (e.g. a host-managed Claude session) but you have a key.
  if (backend === 'sdk') {
    if (apiKey === undefined || apiKey.length === 0) {
      throw new Error(
        'CANVAS_ENGINE_VISION_BACKEND=sdk requires ANTHROPIC_API_KEY to be set',
      );
    }
    return await streamVisionCompletion(
      apiKey,
      buildImageBlock(image),
      instruction,
    );
  }

  // cli / auto: run via the claude CLI (no key needed).
  let tmpPath: string | undefined;
  try {
    tmpPath = await writeTempImage(image);
    const prompt = `Read the screenshot at: ${tmpPath}\n\n${instruction}`;
    return await runClaudeCli({
      system: buildSystemPrompt({ isEdit: false }),
      prompt,
      imagePath: tmpPath,
    });
  } catch (cliError) {
    // auto falls back to the SDK when a key is available; cli never falls back.
    if (backend === 'auto' && apiKey !== undefined && apiKey.length > 0) {
      return await streamVisionCompletion(
        apiKey,
        buildImageBlock(image),
        instruction,
      );
    }
    throw new Error(
      backend === 'cli'
        ? `claude CLI generation failed (CANVAS_ENGINE_VISION_BACKEND=cli, no SDK fallback): ${formatErrorMessage(cliError)}`
        : `claude CLI generation failed and no ANTHROPIC_API_KEY fallback is set: ${formatErrorMessage(cliError)}`,
    );
  } finally {
    if (tmpPath !== undefined) {
      await rm(path.dirname(tmpPath), { recursive: true, force: true }).catch(
        () => undefined,
      );
    }
  }
}

export async function* runImageToClone(
  opts: ImageToCloneOptions,
  deps: ImagePipelineDeps,
): AsyncGenerator<CloneEvent> {
  yield { type: 'status', phase: 'adapt', message: 'preparing vision prompt' };

  const instruction = buildVisionInstruction(opts.intent);
  yield { type: 'preamble', preview: instruction.slice(0, 200) };
  yield {
    type: 'status',
    phase: 'generate',
    message: 'generating code via claude',
  };

  let rawText: string;
  try {
    rawText = await generateCloneCode(opts.image, instruction, deps.apiKey);
  } catch (error) {
    yield { type: 'error', phase: 'generate', message: formatErrorMessage(error) };
    return;
  }

  const { files } = parseStreamedBlocks(rawText);
  const generated: GeneratedFile[] = files.filter(
    (file) => file.content.length > 0,
  );

  if (!generated.some((file) => file.path === 'src/App.jsx')) {
    yield {
      type: 'error',
      phase: 'generate',
      message: 'model did not return a src/App.jsx file block',
    };
    return;
  }

  // Finalize to the Vite sandbox · mirrors url-to-clone.ts finalize, minus the
  // anatomy SessionStore.registerClone (vision clones carry no AnatomyV1
  // envelope, so they don't join the anatomy edit-loop yet).
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
    // Allocation succeeded; release so the Vite server / port / session dir
    // don't leak if seeding fails.
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

  // Register so the clone can be edited later via the LLM edit path. No
  // AnatomyV1 envelope (this is a vision clone), so it skips the region edit-loop.
  deps.store?.registerClone({
    sessionId: session.sessionId,
    source: 'image',
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
