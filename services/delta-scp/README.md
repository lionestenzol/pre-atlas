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

## Turnkey local deploy

Drop your credentials in a `.env` and run one command — no manual `psql`:

```bash
npm install
cp .env.example .env          # fill in the values below
npm run deploy                # applies the schema, then runs gateway + worker
```

`npm run deploy` = `npm run migrate` (apply migrations 004 + 005 to your DB) then
`npm start`. The service auto-loads `.env` from the service root, so once the
file is on disk it "just works" — anything already in the shell environment wins.

`.env` essentials:

| Var | Needed for | Where to find it (Supabase) |
| --- | --- | --- |
| `SUPABASE_URL` | runtime | Project Settings → API → Project URL |
| `SUPABASE_SERVICE_KEY` | runtime | Project Settings → API → `service_role` key |
| `SUPABASE_DB_URL` | `npm run migrate` only | Project Settings → Database → Connection string (URI) |
| `SCP_API_KEY` | gateway auth | any secret you choose (without it `/jobs` returns 503) |

### Steps individually

```bash
npm run migrate   # apply the schema (idempotent; safe to re-run)
npm start         # API gateway + worker in one process
# or split them:
npm run api
npm run worker
```

`npm run migrate` creates `scp_jobs`, the poll/status indexes, the `updated_at`
trigger, `claim_scp_job()` (race-free claiming) and `reap_stale_scp_jobs()`
(crashed-worker recovery). It needs `SUPABASE_DB_URL`; the runtime needs only
`SUPABASE_URL` + `SUPABASE_SERVICE_KEY`. You can still apply the SQL by hand
(`psql "$SUPABASE_DB_URL" -f ../../migrations/004_scp_compression_queue.sql`,
then `005_…`) or paste it into the Supabase SQL editor if you prefer.

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
