# delta-scp — Delta SCP Compression Queue

Async pipeline that turns a **repository URL** into a **compact symbolic JSON
map** (the *Delta SCP — Symbolic Compression Protocol*), via a Supabase-backed
job queue.

```
POST /jobs {repo_url}  ─►  scp_jobs (pending)
                              │  claim_scp_job()  (atomic, SKIP LOCKED)
                              ▼
                          worker  ──►  git clone --depth 1
                              │         walk source files
                              │         extract symbols  (DELTA SCP)
                              ▼
                          scp_jobs (complete, compressed_state JSONB)
                              ▲
GET /jobs/:id  ◄──────────────┘
```

## What "compression" means

Instead of shipping every byte of a repo to a downstream consumer (e.g. an LLM
context window), the protocol emits a **structural skeleton**: the file tree plus
the top-level symbols (functions, classes, interfaces, exports) of each source
file. A large repo collapses to a small JSON map, and the result reports the
estimated **token yield** (tokens saved vs. shipping raw source).

Symbol extraction is heuristic (lightweight per-language regexes, not a full
AST) — cheap, deterministic, and language-agnostic across TS/JS, Python, Go,
Rust, Java, Ruby, and more.

## Layout

| File | Role |
| --- | --- |
| `src/config.ts` | Env-driven configuration |
| `src/supabase.ts` | Service-role Supabase client |
| `src/queue.ts` | Enqueue + **atomic claim** + reaper + state transitions |
| `src/compressor.ts` | Pure DELTA SCP protocol (`compressTree`) |
| `src/source.ts` | Fetch (clone/local) + walk → `compressRepository` |
| `src/validate.ts` | Repo URL guardrails (SSRF / abuse protection) |
| `src/auth.ts` | API-key middleware for the gateway |
| `src/worker.ts` | The agentic loop (drain queue, reap orphans, idle, retry) |
| `src/server.ts` | API gateway (Express) |
| `src/index.ts` | Runs worker + gateway together |
| `src/cli.ts` | Offline one-shot compression (no DB) |
| `test/queue.integration.test.ts` | Real-Postgres tests for claim + reaper |

## Deploy

1. **Schema** — apply both migrations to your Supabase project (it is Postgres):

   ```bash
   psql "$SUPABASE_DB_URL" -f ../../migrations/004_scp_compression_queue.sql
   psql "$SUPABASE_DB_URL" -f ../../migrations/005_scp_reaper.sql
   # or paste them into the Supabase SQL editor
   ```

   004 creates `scp_jobs`, the poll/status indexes, an `updated_at` trigger, and
   the `claim_scp_job()` function (race-free claiming). 005 adds
   `reap_stale_scp_jobs()` for crashed-worker recovery.

2. **Config** — `cp .env.example .env` and fill in `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, and `SCP_API_KEY` (without the API key the `/jobs`
   routes stay disabled and return 503).

3. **Run** — `npm install` then:

   ```bash
   npm start        # API gateway + worker in one process
   # or split them:
   npm run api
   npm run worker
   ```

4. **Feed a repo URL → get compressed JSON:**

   ```bash
   curl -s -XPOST localhost:3012/jobs \
     -H 'content-type: application/json' \
     -H "authorization: Bearer $SCP_API_KEY" \
     -d '{"repo_url":"https://github.com/owner/repo.git"}'
   # → { "ok": true, "job": { "id": "...", "status": "pending", ... } }

   curl -s localhost:3012/jobs/<id> -H "authorization: Bearer $SCP_API_KEY" \
     | jq .job.compressed_state
   ```

   `repo_url` is validated before enqueue: only `https`/`git`/`ssh` (and
   scp-like `git@host:…`) URLs are accepted, private/loopback/metadata hosts are
   refused, and `SCP_ALLOWED_HOSTS` can pin it to specific hosts.

## Offline / no Supabase

Try the protocol directly against any local path or git URL:

```bash
npm run compress -- /path/to/repo out.json
npm run compress -- https://github.com/owner/repo.git
```

## Test

```bash
npm test
```

- `src/compressor.test.ts` — pure DELTA SCP logic, no network/DB needed.
- `test/queue.integration.test.ts` — spins up a throwaway Postgres cluster,
  applies migrations 004 + 005, and proves `claim_scp_job()` never double-claims
  under concurrency and that `reap_stale_scp_jobs()` re-queues orphans. It
  **skips automatically** when Postgres server binaries are unavailable. (When
  running as root it drives the cluster as the `postgres` system user, since
  Postgres refuses to run as root.)

## Notes vs. the original sketch

The first draft polled with `setInterval(poll, 5000)` and claimed jobs with a
non-atomic select-then-update. This implementation fixes:

- **Race condition** — `claim_scp_job()` uses `FOR UPDATE SKIP LOCKED`, so
  concurrent workers can never claim the same job.
- **Empty-queue crash** — `.single()` throws on zero rows; the claim RPC simply
  returns no rows.
- **Overlapping runs** — a self-rescheduling loop replaces `setInterval`, so a
  slow job never overlaps the next poll, and the queue drains back-to-back
  instead of one-job-per-5s.
- **Lost failures** — failed jobs re-queue with attempt accounting and park in
  `error` once `max_attempts` is exhausted.
- **Crashed-worker recovery** — `reap_stale_scp_jobs()` re-queues jobs orphaned
  in `processing` (a crash never hits the failJob path), run on an interval by
  the worker.
- **Closed by default** — the gateway requires an API key and validates every
  `repo_url` (scheme + host) before it can reach `git clone`.
- **Real compressor** — the `compressRepository` stub is replaced with an actual
  clone + walk + symbol-extraction pipeline.
