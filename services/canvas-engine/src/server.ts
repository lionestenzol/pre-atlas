import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express, { type Request, type Response } from 'express';
import { z } from 'zod';
import { generateStub, type StreamEvent } from './vendor/lovable/generate.js';
import { VENDOR_INFO } from './vendor/lovable/VENDOR_SHA.js';
import { VitePool } from './sandbox/vite-pool.js';
import { SitepullResolver } from './pipeline/sitepull-resolver.js';
import { runUrlToClone, type CloneEvent } from './pipeline/url-to-clone.js';
import { SessionStore } from './pipeline/session-store.js';
import { runEdit, type EditEventStream } from './pipeline/edit-loop.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const WEB_AUDIT_ROOT = process.env.WEB_AUDIT_ROOT ?? 'C:/Users/bruke/web-audit';
const TEMPLATE_DIR = path.join(PROJECT_ROOT, 'sandbox-template');
const SESSIONS_DIR = path.join(PROJECT_ROOT, '.canvas-sessions');
const PORT = Number(process.env.CANVAS_ENGINE_PORT ?? 3050);
const VERSION = '0.1.0';
const PHASE = 3;

const cloneRequestSchema = z.object({
  url: z.string().url(),
  intent: z.string().optional(),
});

const editRequestSchema = z.object({
  sessionId: z.string().min(1),
  targetId: z.string().min(1),
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
app.use(express.json({ limit: '2mb' }));

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

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  try {
    for await (const event of runUrlToClone(body, {
      pool,
      resolveCapture: (url) => resolver.resolve(url),
      store,
    })) {
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

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  try {
    for await (const event of runEdit(body, { pool, store })) {
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

app.delete('/sessions/:sessionId', async (req: Request, res: Response) => {
  const { sessionId } = req.params as { sessionId: string };
  await pool.release(sessionId);
  store.remove(sessionId);
  res.json({ ok: true });
});

const server = app.listen(PORT, () => {
  console.log(`[canvas-engine] listening on http://localhost:${PORT}`);
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
