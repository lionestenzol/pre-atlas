-- Migration 004: Delta SCP Compression Queue
-- Async job queue for the Delta SCP (Symbolic Compression Protocol) pipeline.
-- A worker pulls a repo_url job, compresses the repository into a compact
-- symbolic JSON map, and writes the result back.
--
-- Postgres-native: applies cleanly to the aegis_admin PostgreSQL instance and
-- to a Supabase project (Supabase is Postgres). gen_random_uuid() requires
-- the pgcrypto extension, which Supabase enables by default; for a bare
-- Postgres run `CREATE EXTENSION IF NOT EXISTS pgcrypto;` first.

CREATE TABLE IF NOT EXISTS scp_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_url         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',  -- pending | processing | complete | error
    compressed_state JSONB,
    error_log        TEXT,
    attempt          INT  NOT NULL DEFAULT 0,
    max_attempts     INT  NOT NULL DEFAULT 3,
    claimed_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT scp_jobs_status_chk
        CHECK (status IN ('pending', 'processing', 'complete', 'error'))
);

-- Poll index: fast claim of the oldest pending job (partial → only pending rows).
CREATE INDEX IF NOT EXISTS idx_scp_jobs_poll
    ON scp_jobs (created_at ASC)
    WHERE status = 'pending';

-- Status index: fast counts for dashboard / health stats.
CREATE INDEX IF NOT EXISTS idx_scp_jobs_status
    ON scp_jobs (status);

-- Keep updated_at fresh on every mutation.
CREATE OR REPLACE FUNCTION scp_jobs_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_scp_jobs_touch ON scp_jobs;
CREATE TRIGGER trg_scp_jobs_touch
    BEFORE UPDATE ON scp_jobs
    FOR EACH ROW
    EXECUTE FUNCTION scp_jobs_touch_updated_at();

-- Atomic claim: select the oldest pending job and flip it to 'processing' in a
-- single statement. FOR UPDATE SKIP LOCKED makes concurrent workers safe — no
-- two workers can ever claim the same job (the bug in a naive select-then-update
-- queue). Returns the claimed row, or no rows when the queue is empty.
-- Call from the worker via supabase.rpc('claim_scp_job').
CREATE OR REPLACE FUNCTION claim_scp_job()
RETURNS SETOF scp_jobs AS $$
    UPDATE scp_jobs
    SET status     = 'processing',
        claimed_at = NOW(),
        attempt    = attempt + 1
    WHERE id = (
        SELECT id
        FROM scp_jobs
        WHERE status = 'pending'
        ORDER BY created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING *;
$$ LANGUAGE sql;
