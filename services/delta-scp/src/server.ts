// Delta SCP · API gateway
//
//   POST /jobs        { "repo_url": "..." }  -> enqueue, returns the job row
//   GET  /jobs/:id                            -> job status + compressed_state
//   GET  /healthz                             -> liveness

import express from 'express';
import { loadConfig } from './config.js';
import { getSupabase } from './supabase.js';
import { enqueueJob, getJob } from './queue.js';

export function createServer() {
  const app = express();
  app.use(express.json({ limit: '256kb' }));
  const db = getSupabase();

  app.get('/healthz', (_req, res) => {
    res.json({ ok: true, service: 'delta-scp' });
  });

  app.post('/jobs', async (req, res) => {
    const repoUrl = (req.body?.repo_url ?? '').toString().trim();
    if (!repoUrl) {
      res.status(400).json({ ok: false, error: 'repo_url is required' });
      return;
    }
    try {
      const job = await enqueueJob(db, repoUrl);
      res.status(201).json({ ok: true, job });
    } catch (err) {
      res.status(500).json({ ok: false, error: String(err) });
    }
  });

  app.get('/jobs/:id', async (req, res) => {
    try {
      const job = await getJob(db, req.params.id);
      if (!job) {
        res.status(404).json({ ok: false, error: 'job not found' });
        return;
      }
      res.json({ ok: true, job });
    } catch (err) {
      res.status(500).json({ ok: false, error: String(err) });
    }
  });

  return app;
}

export function startServer() {
  const config = loadConfig();
  const app = createServer();
  return app.listen(config.port, () => {
    console.log(`[delta-scp] API gateway listening on :${config.port}`);
  });
}

// Direct entry: `npm run api`
if (import.meta.url === `file://${process.argv[1]}`) {
  startServer();
}
