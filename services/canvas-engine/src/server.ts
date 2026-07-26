import './load-env.js'; // MUST be first: loads .env before any process.env read
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express, { type Request, type Response } from 'express';
import { z } from 'zod';
import { generateStub, type StreamEvent } from './vendor/lovable/generate.js';
import { VENDOR_INFO } from './vendor/lovable/VENDOR_SHA.js';
import { VitePool } from './sandbox/vite-pool.js';
import { SitepullResolver } from './pipeline/sitepull-resolver.js';
import { runUrlToClone, type CloneEvent } from './pipeline/url-to-clone.js';
import { runImageToClone } from './pipeline/image-to-clone.js';
import { runImageToEnvelope } from './pipeline/image-to-envelope.js';
import { runImageToCloneGuided } from './pipeline/image-to-clone-guided.js';
import { SessionStore } from './pipeline/session-store.js';
import { runEdit, type EditEventStream } from './pipeline/edit-loop.js';
import { runImageEdit } from './pipeline/image-edit.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const WEB_AUDIT_ROOT = process.env.WEB_AUDIT_ROOT ?? 'C:/Users/bruke/web-audit';
const TEMPLATE_DIR = path.join(PROJECT_ROOT, 'sandbox-template');
const SESSIONS_DIR = path.join(PROJECT_ROOT, '.canvas-sessions');
const PORT = Number(process.env.CANVAS_ENGINE_PORT ?? 3050);
const VERSION = '0.1.0';
const PHASE = 3;

const cloneRequestSchema = z
  .object({
    url: z.string().url().optional(),
    image: z.string().min(1).optional(),
    intent: z.string().optional(),
    // image path only · how to clone a screenshot:
    //   'vision'    = pixel-faithful LLM→code (default · the diagonal shortcut)
    //   'structure' = LLM→envelope→deterministic skeleton (structure, canonical)
    //   'fused'     = LLM→envelope, then structure-guided vision codegen
    //                 (1:1 look + structure · the hub fusion)
    via: z.enum(['vision', 'structure', 'fused']).optional(),
  })
  .refine((body) => (body.url ? 1 : 0) + (body.image ? 1 : 0) === 1, {
    message: 'provide exactly one of "url" or "image"',
  });

const editRequestSchema = z.object({
  sessionId: z.string().min(1),
  targetId: z.string().min(1).optional(),
  intent: z.string().min(1),
});

const stubRequestSchema = z.object({
  url: z.string().url().optional(),
  prompt: z.string().optional(),
  isEdit: z.boolean().optional(),
});

const pool = new VitePool({
  templateDir: TEMPLATE_DIR,
  sessionsDir: SESSIONS_DIR,
  portRange: [3060, 3069],
});

const resolver = new SitepullResolver({ webAuditRoot: WEB_AUDIT_ROOT });
const store = new SessionStore();

function writeSseEvent(
  res: Response,
  event: CloneEvent | StreamEvent | EditEventStream,
): void {
  res.write(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
}

const app = express();
// 16mb · base64 screenshots for the /clone image (vision) path can be several MB
app.use(express.json({ limit: '16mb' }));

app.get('/health', (_req: Request, res: Response) => {
  res.json({
    ok: true,
    service: 'canvas-engine',
    version: VERSION,
    phase: PHASE,
    port: PORT,
    vendor: VENDOR_INFO,
    sessions: pool.listActive(),
  });
});

app.get('/sessions', (_req: Request, res: Response) => {
  res.json({ sessions: pool.listActive() });
});

app.post('/clone/stub', async (req: Request, res: Response) => {
  let body: z.infer<typeof stubRequestSchema>;
  try {
    body = stubRequestSchema.parse(req.body ?? {});
  } catch (err) {
    res.status(400).json({
      ok: false,
      error: 'invalid_request',
      detail: err instanceof Error ? err.message : 'unknown',
    });
    return;
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  try {
    for await (const event of generateStub(body)) {
      writeSseEvent(res, event);
    }
  } finally {
    res.end();
  }
});

app.post('/clone', async (req: Request, res: Response) => {
  let body: z.infer<typeof cloneRequestSchema>;
  try {
    body = cloneRequestSchema.parse(req.body ?? {});
  } catch (err) {
    res.status(400).json({
      ok: false,
      error: 'invalid_request',
      detail: err instanceof Error ? err.message : 'unknown',
    });
    return;
  }

  // The image (vision) path uses the claude CLI by default (no key). An API key
  // is only an optional SDK fallback; empty string -> undefined so it's not
  // mistaken for a real key.
  const anthropicApiKey = process.env.ANTHROPIC_API_KEY || undefined;

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  try {
    const imageDeps = { pool, apiKey: anthropicApiKey, store };
    let events: AsyncGenerator<CloneEvent>;
    if (body.image !== undefined) {
      const imageOpts = { image: body.image, intent: body.intent };
      events =
        body.via === 'structure'
          ? runImageToEnvelope(imageOpts, imageDeps)
          : body.via === 'fused'
            ? runImageToCloneGuided(imageOpts, imageDeps)
            : runImageToClone(imageOpts, imageDeps);
    } else {
      events = runUrlToClone(
        { url: body.url as string, intent: body.intent },
        { pool, resolveCapture: (url) => resolver.resolve(url), store },
      );
    }

    for await (const event of events) {
      writeSseEvent(res, event);
    }
  } catch (err) {
    writeSseEvent(res, {
      type: 'error',
      phase: 'unknown',
      message: err instanceof Error ? err.message : 'unknown',
    });
  } finally {
    res.end();
  }
});

app.post('/edit', async (req: Request, res: Response) => {
  let body: z.infer<typeof editRequestSchema>;
  try {
    body = editRequestSchema.parse(req.body ?? {});
  } catch (err) {
    res.status(400).json({
      ok: false,
      error: 'invalid_request',
      detail: err instanceof Error ? err.message : 'unknown',
    });
    return;
  }

  const state = store.getState(body.sessionId);
  if (state === undefined) {
    res.status(404).json({ ok: false, error: 'session_not_found' });
    return;
  }

  // A clone carrying an AnatomyV1 envelope (url clones, and image clones cloned
  // via the structure/envelope path) uses the deterministic region edit-loop,
  // which needs a targetId. An envelope-less vision clone edits via the claude
  // CLI free-form path (no key; key is optional SDK fallback).
  const anthropicApiKey = process.env.ANTHROPIC_API_KEY || undefined;
  // Deterministic region edit-loop only when the JSX was deterministically
  // emitted (url + structure-image). AI-authored clones (vision + fused) edit via
  // the free-form claude path even if they carry an envelope (the map).
  const useDeterministic =
    state.envelope !== undefined && state.generator !== 'llm';
  if (useDeterministic && (body.targetId ?? '').length === 0) {
    res.status(400).json({
      ok: false,
      error: 'missing_target',
      detail: 'deterministic clones require a targetId (region/chain id) to edit.',
    });
    return;
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  try {
    const events: AsyncGenerator<EditEventStream> = useDeterministic
      ? runEdit(
          {
            sessionId: body.sessionId,
            targetId: body.targetId as string,
            intent: body.intent,
          },
          { pool, store },
        )
      : runImageEdit(
          { sessionId: body.sessionId, intent: body.intent },
          { pool, store, apiKey: anthropicApiKey },
        );

    for await (const event of events) {
      writeSseEvent(res, event);
    }
  } catch (err) {
    writeSseEvent(res, {
      type: 'error',
      phase: 'unknown',
      message: err instanceof Error ? err.message : 'unknown',
    });
  } finally {
    res.end();
  }
});

app.get('/sessions/:sessionId/edits', (req: Request, res: Response) => {
  const { sessionId } = req.params as { sessionId: string };
  const state = store.getState(sessionId);
  if (state === undefined) {
    res.status(404).json({ ok: false, error: 'session_not_found' });
    return;
  }
  res.json({ sessionId, edits: state.edits });
});

// The "map": the AnatomyV1 envelope behind a clone. Present for url clones and
// for image clones cloned via the structure/envelope path; absent for vision
// (pixel-faithful) image clones.
app.get('/sessions/:sessionId/envelope', (req: Request, res: Response) => {
  const { sessionId } = req.params as { sessionId: string };
  const state = store.getState(sessionId);
  if (state === undefined) {
    res.status(404).json({ ok: false, error: 'session_not_found' });
    return;
  }
  if (state.envelope === undefined) {
    res.status(409).json({
      ok: false,
      error: 'no_envelope',
      detail: 'this clone has no anatomy envelope (vision image clone).',
    });
    return;
  }
  res.json({
    ok: true,
    sessionId,
    source: state.source,
    envelope: state.envelope,
  });
});

app.delete('/sessions/:sessionId', async (req: Request, res: Response) => {
  const { sessionId } = req.params as { sessionId: string };
  await pool.release(sessionId);
  store.remove(sessionId);
  res.json({ ok: true });
});

const server = app.listen(PORT, '127.0.0.1', () => {
  console.log(`[canvas-engine] listening on http://127.0.0.1:${PORT}`);
  console.log(`[canvas-engine] phase ${PHASE} · version ${VERSION}`);
  console.log(`[canvas-engine] vendor ${VENDOR_INFO.repo}@${VENDOR_INFO.sha.slice(0, 12)}`);
  console.log(`[canvas-engine] vite pool ports 3060-3069 · template ${TEMPLATE_DIR}`);
  console.log(`[canvas-engine] web-audit root ${WEB_AUDIT_ROOT}`);
});

const shutdown = async (): Promise<void> => {
  console.log('[canvas-engine] shutting down · releasing all sessions');
  await pool.shutdown();
  server.close(() => process.exit(0));
};

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
