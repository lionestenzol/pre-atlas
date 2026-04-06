-- Migration 003: Execution Queue
-- Adds a persistent job queue for async task execution.
-- Applied to the aegis_admin database (same PostgreSQL instance).

CREATE TABLE IF NOT EXISTS execution_queue (
    job_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id      TEXT NOT NULL,
    executor     TEXT NOT NULL DEFAULT 'claude',
    status       TEXT NOT NULL DEFAULT 'pending',
    priority     INT NOT NULL DEFAULT 1,
    payload      JSONB NOT NULL,
    result       JSONB,
    error        TEXT,
    claimed_by   TEXT,
    claimed_at   TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    attempt      INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    timeout_secs INT NOT NULL DEFAULT 300,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Poll index: fast claim of highest-priority pending jobs
CREATE INDEX IF NOT EXISTS idx_eq_poll
    ON execution_queue (priority DESC, created_at ASC)
    WHERE status = 'pending';

-- Heartbeat index: find stale running jobs for reaping
CREATE INDEX IF NOT EXISTS idx_eq_heartbeat
    ON execution_queue (heartbeat_at)
    WHERE status IN ('claimed', 'running');

-- Status index: fast counts for dashboard stats
CREATE INDEX IF NOT EXISTS idx_eq_status
    ON execution_queue (status);
