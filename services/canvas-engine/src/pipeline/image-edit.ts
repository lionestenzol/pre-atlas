// canvas-engine · image-clone edit path · LLM free-form edits on a vision clone
//
// Image clones carry no AnatomyV1 envelope, so they can't use the region-based
// deterministic edit-loop (edit-loop.ts). Instead this sends the current sandbox
// files plus the user's intent to Claude using open-lovable's isEdit system
// prompt, then writes back the complete <file> blocks it returns. Mirrors abi's
// "update" flow. Emits the same EditEventStream shape as the URL edit path.

import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

import Anthropic from '@anthropic-ai/sdk';

import { parseStreamedBlocks } from '../vendor/lovable/parse-blocks.js';
import { buildSystemPrompt } from '../vendor/lovable/system-prompt.js';
import type { VitePool } from '../sandbox/vite-pool.js';
import { runClaudeCli } from './claude-cli.js';
import { resolveVisionBackend } from './vision-backend.js';
import type { EditEventStream } from './edit-loop.js';
import type { SessionStore } from './session-store.js';

const DEFAULT_VISION_MODEL =
  process.env.CANVAS_ENGINE_VISION_MODEL ?? 'claude-sonnet-4-6';
const MAX_OUTPUT_TOKENS = 16000;
const EDITABLE_FILE = /\.(jsx?|tsx?|css)$/;

export interface ImageEditOptions {
  sessionId: string;
  intent: string;
}

export interface ImageEditDeps {
  pool: VitePool;
  store: SessionStore;
  /** Optional SDK fallback key. The CLI backend (default) needs no key. */
  apiKey?: string;
}

interface SandboxFile {
  path: string; // root-relative, forward-slashed (e.g. src/App.jsx)
  content: string;
}

function formatErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function readSandboxFiles(rootDir: string): Promise<SandboxFile[]> {
  const out: SandboxFile[] = [];
  const walk = async (dir: string): Promise<void> => {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(abs);
        continue;
      }
      if (!EDITABLE_FILE.test(entry.name)) {
        continue;
      }
      const content = await readFile(abs, 'utf8');
      const rel = path.relative(rootDir, abs).split(path.sep).join('/');
      out.push({ path: rel, content });
    }
  };
  await walk(path.join(rootDir, 'src'));
  return out;
}

function buildEditUserMessage(current: SandboxFile[], intent: string): string {
  const fileBlocks = current
    .map((file) => `<file path="${file.path}">\n${file.content}\n</file>`)
    .join('\n\n');
  return `These are the current files of the app (a React + Vite + Tailwind project):

${fileBlocks}

Requested change:
${intent}

Apply ONLY the requested change. Return the COMPLETE updated file(s) in <file path="..."></file> blocks — include every line, no ellipsis. Do not return files that do not change. Do not create config files (vite/tailwind/package).`;
}

async function streamEditCompletion(
  apiKey: string,
  current: SandboxFile[],
  intent: string,
): Promise<string> {
  const client = new Anthropic({ apiKey });
  const stream = client.messages.stream({
    model: DEFAULT_VISION_MODEL,
    max_tokens: MAX_OUTPUT_TOKENS,
    system: buildSystemPrompt({ isEdit: true }),
    messages: [
      { role: 'user', content: buildEditUserMessage(current, intent) },
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

// Edit. Backend chosen by CANVAS_ENGINE_VISION_BACKEND:
//   - 'sdk'  → call the Anthropic API directly (requires a key)
//   - 'cli'  → claude CLI only, no fallback
//   - 'auto' → claude CLI first (no key), SDK fallback if the CLI fails and a
//              key is configured. (default)
async function generateEditCode(
  current: SandboxFile[],
  intent: string,
  apiKey?: string,
): Promise<string> {
  const backend = resolveVisionBackend();

  if (backend === 'sdk') {
    if (apiKey === undefined || apiKey.length === 0) {
      throw new Error(
        'CANVAS_ENGINE_VISION_BACKEND=sdk requires ANTHROPIC_API_KEY to be set',
      );
    }
    return await streamEditCompletion(apiKey, current, intent);
  }

  try {
    return await runClaudeCli({
      system: buildSystemPrompt({ isEdit: true }),
      prompt: buildEditUserMessage(current, intent),
    });
  } catch (cliError) {
    // auto falls back to the SDK when a key is available; cli never falls back.
    if (backend === 'auto' && apiKey !== undefined && apiKey.length > 0) {
      return await streamEditCompletion(apiKey, current, intent);
    }
    throw new Error(
      backend === 'cli'
        ? `claude CLI edit failed (CANVAS_ENGINE_VISION_BACKEND=cli, no SDK fallback): ${formatErrorMessage(cliError)}`
        : `claude CLI edit failed and no ANTHROPIC_API_KEY fallback is set: ${formatErrorMessage(cliError)}`,
    );
  }
}

export async function* runImageEdit(
  opts: ImageEditOptions,
  deps: ImageEditDeps,
): AsyncGenerator<EditEventStream> {
  yield {
    type: 'status',
    phase: 'resolve',
    message: `resolving image clone ${opts.sessionId}`,
  };

  const state = deps.store.getState(opts.sessionId);
  if (state === undefined) {
    yield {
      type: 'error',
      phase: 'resolve',
      message: `session ${opts.sessionId} not found in store`,
    };
    return;
  }
  if (deps.pool.getSession(opts.sessionId) === undefined) {
    yield {
      type: 'error',
      phase: 'resolve',
      message: `session ${opts.sessionId} not active in pool`,
    };
    return;
  }

  let current: SandboxFile[];
  try {
    current = await readSandboxFiles(state.rootDir);
  } catch (error) {
    yield { type: 'error', phase: 'resolve', message: formatErrorMessage(error) };
    return;
  }
  if (current.length === 0) {
    yield {
      type: 'error',
      phase: 'resolve',
      message: 'no source files found for this clone',
    };
    return;
  }

  yield {
    type: 'status',
    phase: 'edit-prompt',
    message: 'editing via claude',
  };

  let rawText: string;
  try {
    rawText = await generateEditCode(current, opts.intent, deps.apiKey);
  } catch (error) {
    const message = formatErrorMessage(error);
    yield { type: 'error', phase: 'apply', message };
    deps.store.recordEdit(opts.sessionId, {
      timestamp: Date.now(),
      intent: opts.intent,
      targetId: '',
      outcome: 'error',
      filesChanged: [],
      message,
    });
    return;
  }

  const { files } = parseStreamedBlocks(rawText);
  const changed = files.filter((file) => file.content.length > 0);

  if (changed.length === 0) {
    deps.store.recordEdit(opts.sessionId, {
      timestamp: Date.now(),
      intent: opts.intent,
      targetId: '',
      outcome: 'noop',
      filesChanged: [],
      message: 'model returned no file blocks',
    });
    yield { type: 'status', phase: 'done', message: 'no changes returned' };
    yield {
      type: 'done',
      sessionId: opts.sessionId,
      url: state.url,
      intent: opts.intent,
      targetId: '',
      outcome: 'noop',
      filesChanged: [],
    };
    return;
  }

  yield {
    type: 'status',
    phase: 'apply',
    message: `writing ${changed.length} file(s)`,
  };

  try {
    await deps.pool.writeFiles(opts.sessionId, changed);
  } catch (error) {
    const message = formatErrorMessage(error);
    yield { type: 'error', phase: 'apply', message };
    deps.store.recordEdit(opts.sessionId, {
      timestamp: Date.now(),
      intent: opts.intent,
      targetId: '',
      outcome: 'error',
      filesChanged: [],
      message,
    });
    return;
  }

  for (const file of changed) {
    yield { type: 'file', path: file.path, content: file.content };
  }

  const filesChanged = changed.map((file) => file.path);
  deps.store.recordEdit(opts.sessionId, {
    timestamp: Date.now(),
    intent: opts.intent,
    targetId: '',
    outcome: 'applied',
    filesChanged,
  });

  yield {
    type: 'status',
    phase: 'done',
    message: `applied · ${filesChanged.length} file(s) changed`,
  };
  yield {
    type: 'done',
    sessionId: opts.sessionId,
    url: state.url,
    intent: opts.intent,
    targetId: '',
    outcome: 'applied',
    filesChanged,
  };
}
