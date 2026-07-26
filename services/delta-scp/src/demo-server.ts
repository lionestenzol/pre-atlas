// Delta SCP · demo gateway (Supabase-free, synchronous)
//
// A thin HTTP adapter that puts the REAL compression engine behind :3012 so the
// web UI has a live service to validate against without a Supabase-backed queue.
//
// It REUSES the engine unchanged — `compressRepository` (source.ts → compressor.ts)
// and `buildGraphRows` (graph.ts) — and returns the same `compressed_state` shape
// the production worker writes, plus the AST graph layer (which the production
// HTTP gateway does NOT expose). It does NOT modify or replace the real gateway
// (server.ts); run that instead once Supabase creds are configured.
//
//   GET  /healthz                  -> liveness (parity with server.ts)
//   POST /jobs    { repo_url }      -> compress synchronously, return a COMPLETE job
//   GET  /jobs/:id                  -> fetch a previously computed job (in-memory)
//
// The UI talks the same POST/GET-/jobs contract it would against the real queue;
// only the transport differs (sync result vs. poll-until-complete). Auth mirrors
// the real gateway but is optional here: set SCP_API_KEY to require a Bearer key.

import express from 'express';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { loadConfig, type ScpConfig } from './config.js';
import { fetchSourceFiles } from './source.js';
import { compressTree } from './compressor.js';
import { buildGraphRows } from './graph.js';
import { validateRepoUrl } from './validate.js';

function intEnv(name: string, fallback: number): number {
  const v = Number(process.env[name]);
  return Number.isFinite(v) && v > 0 ? Math.trunc(v) : fallback;
}

// Public-facing abuse limits (env-overridable). Strangers can hit this, and each
// /jobs does a real `git clone`, so the limits are deliberately conservative.
const RATE_WINDOW_MS = intEnv('SCP_RATE_WINDOW_MS', 5 * 60 * 1000); // 5 min
const RATE_MAX = intEnv('SCP_RATE_MAX', 15); // requests per window per IP
const MAX_INFLIGHT = intEnv('SCP_MAX_INFLIGHT', 3); // concurrent clones (reject beyond)

// Tighter source caps for a public demo than the engine's batch defaults — a
// hostile or huge repo can't exhaust disk/CPU or balloon the JSON to the browser.
function withDemoCaps(config: ScpConfig): ScpConfig {
  return {
    ...config,
    maxFiles: intEnv('SCP_MAX_FILES', Math.min(config.maxFiles, 4000)),
    maxTotalBytes: intEnv('SCP_MAX_TOTAL_BYTES', Math.min(config.maxTotalBytes, 8 * 1024 * 1024)),
    maxFileBytes: intEnv('SCP_MAX_FILE_BYTES', Math.min(config.maxFileBytes, 512 * 1024)),
  };
}

interface DemoJob {
  id: string;
  repo_url: string;
  status: 'complete' | 'error';
  compressed_state: Record<string, unknown> | null;
  graph: GraphSummary | null;
  error_log: string | null;
  created_at: string;
  updated_at: string;
}

interface GraphSummary {
  node_count: number;
  edge_count: number;
  // Resolved file→file import edges (the readable slice of the AST graph).
  imports: Array<{ from: string; to: string }>;
  node_types: Record<string, number>;
}

// Reduce buildGraphRows() output to the display-ready graph-memory summary. The
// production reader (readFocusFromGraph) walks these same import edges in Supabase;
// here we surface them straight from the pure builder.
function summarizeGraph(repo: string, files: Parameters<typeof buildGraphRows>[1]): GraphSummary {
  const { nodes, edges } = buildGraphRows(repo, files);
  const nodeTypes: Record<string, number> = {};
  for (const n of nodes) nodeTypes[n.node_type] = (nodeTypes[n.node_type] ?? 0) + 1;
  return {
    node_count: nodes.length,
    edge_count: edges.length,
    imports: edges.map((e) => ({ from: e.source.file_path, to: e.target.file_path })),
    node_types: nodeTypes,
  };
}

export function createDemoServer(baseConfig: ScpConfig = loadConfig()) {
  const config = withDemoCaps(baseConfig);
  const app = express();
  app.disable('x-powered-by');
  // Behind the Vite dev proxy / a hosting proxy: trust one hop so rate-limiting
  // keys on the real client IP (X-Forwarded-For) rather than the proxy's.
  app.set('trust proxy', 1);
  // Security headers (CSP/HSTS/frameguard/noSniff/etc). Responses are JSON, so
  // CSP doesn't interfere with the separately-served UI.
  app.use(helmet());
  app.use(express.json({ limit: '32kb' })); // bodies are tiny ({repo_url})
  const jobs = new Map<string, DemoJob>();

  // Per-IP rate limit on the expensive route. Standardized RateLimit-* headers.
  const jobsLimiter = rateLimit({
    windowMs: RATE_WINDOW_MS,
    max: RATE_MAX,
    standardHeaders: true,
    legacyHeaders: false,
    message: { ok: false, error: 'rate limit exceeded — please slow down and retry shortly' },
  });

  // Reject-when-busy concurrency gate: clones are heavy, so cap concurrent work
  // and return a fast 429 instead of queueing (a queue would let load pile up).
  let inFlight = 0;

  // Optional Bearer auth — only enforced when SCP_API_KEY is set.
  app.use((req, res, next) => {
    if (!config.apiKey) return next();
    const header = req.header('authorization') ?? '';
    const key = header.replace(/^Bearer\s+/i, '') || req.header('x-api-key') || '';
    if (key !== config.apiKey) {
      res.status(401).json({ ok: false, error: 'invalid or missing API key' });
      return;
    }
    next();
  });

  app.get('/healthz', (_req, res) => {
    res.json({ ok: true, service: 'delta-scp', mode: 'demo' });
  });

  app.post('/jobs', jobsLimiter, async (req, res) => {
    const repoUrl = (req.body?.repo_url ?? '').toString().trim();
    if (!repoUrl) {
      res.status(400).json({ ok: false, error: 'repo_url is required' });
      return;
    }
    // SSRF + abuse guard: scheme/host allowlist, private/loopback/metadata refused.
    const verdict = validateRepoUrl(repoUrl, config);
    if (!verdict.ok) {
      res.status(400).json({ ok: false, error: `rejected repo_url: ${verdict.reason}` });
      return;
    }
    // Concurrency gate — fast 429 rather than piling clones onto the box.
    if (inFlight >= MAX_INFLIGHT) {
      res
        .status(429)
        .json({ ok: false, error: 'server busy — too many compressions in progress, retry shortly' });
      return;
    }

    const id = randomUUID();
    const now = new Date().toISOString();
    inFlight++;
    try {
      // Same fetch the worker uses (clone/local → SourceFile[]), then the pure
      // compressor + the pure graph builder. One clone, two derived views.
      const files = await fetchSourceFiles(repoUrl, config);
      const compressed = compressTree(repoUrl, files, now);
      const graph = summarizeGraph(repoUrl, files);
      const job: DemoJob = {
        id,
        repo_url: repoUrl,
        status: 'complete',
        compressed_state: compressed,
        graph,
        error_log: null,
        created_at: now,
        updated_at: new Date().toISOString(),
      };
      jobs.set(id, job);
      res.status(201).json({ ok: true, job });
    } catch (err) {
      const message = String(err instanceof Error ? err.message : err)
        .replace(/\/\/[^/@\s]+@/g, '//***@')
        .slice(0, 2000);
      const job: DemoJob = {
        id,
        repo_url: repoUrl,
        status: 'error',
        compressed_state: null,
        graph: null,
        error_log: message,
        created_at: now,
        updated_at: new Date().toISOString(),
      };
      jobs.set(id, job);
      console.error('[delta-scp demo] POST /jobs failed:', message);
      res.status(200).json({ ok: true, job }); // job carries the error, like the queue
    } finally {
      inFlight--; // always release the slot, success or failure
    }
  });

  app.get('/jobs/:id', (req, res) => {
    const job = jobs.get(String(req.params.id));
    if (!job) {
      res.status(404).json({ ok: false, error: 'job not found' });
      return;
    }
    res.json({ ok: true, job });
  });

  return app;
}

export function startDemoServer(config: ScpConfig = loadConfig()) {
  const app = createDemoServer(config);
  return app.listen(config.port, () => {
    console.log(`[delta-scp demo] gateway listening on :${config.port} (Supabase-free)`);
    console.log(
      `[delta-scp demo] limits: ${RATE_MAX} req / ${Math.round(RATE_WINDOW_MS / 60000)}min per IP · ` +
        `${MAX_INFLIGHT} concurrent · helmet on`,
    );
    if (config.apiKey) console.log('[delta-scp demo] Bearer auth ENABLED (SCP_API_KEY set)');
    else console.log('[delta-scp demo] Bearer auth disabled (set SCP_API_KEY to require a key)');
  });
}

// Cross-platform entry check (Windows paths don't match a naive `file://` + argv).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  startDemoServer();
}
