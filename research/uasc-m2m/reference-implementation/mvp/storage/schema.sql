-- UASC-M2M MVP Schema
-- SQLite database for command registry and audit logging

-- Commands registry: maps tokens to execution profiles
CREATE TABLE IF NOT EXISTS commands (
    cmd TEXT PRIMARY KEY,           -- @WORK, @WRAP, etc.
    profile_id TEXT NOT NULL,       -- WORK_v1, WRAP_v1, etc.
    version INTEGER NOT NULL,       -- Current active version
    enabled INTEGER DEFAULT 1,      -- 0=disabled, 1=enabled
    allowed_roles TEXT DEFAULT '*', -- Comma-separated roles or * for all
    checksum TEXT,                  -- SHA256 of profile JSON
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Clients: authorized callers
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,     -- Unique client identifier
    client_name TEXT NOT NULL,      -- Human-readable name
    secret_hash TEXT NOT NULL,      -- SHA256 of shared secret
    roles TEXT DEFAULT 'user',      -- Comma-separated roles
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT
);

-- Runs: execution audit log
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,        -- UUID
    cmd TEXT NOT NULL,              -- Command executed
    profile_id TEXT NOT NULL,       -- Profile used
    version INTEGER NOT NULL,       -- Profile version
    client_id TEXT NOT NULL,        -- Who called it
    status TEXT NOT NULL,           -- pending, running, success, failed
    started_at TEXT DEFAULT (datetime('now')),
    ended_at TEXT,
    duration_ms INTEGER,
    error TEXT,
    FOREIGN KEY (cmd) REFERENCES commands(cmd),
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

-- Run events: step-by-step execution log
CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_idx INTEGER NOT NULL,      -- 0-indexed step number
    step_type TEXT NOT NULL,        -- shell, http, condition, etc.
    event_type TEXT NOT NULL,       -- started, completed, failed, skipped
    payload TEXT,                   -- JSON: command, output, error, etc.
    ts TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_runs_client ON runs(client_id);
CREATE INDEX IF NOT EXISTS idx_runs_cmd ON runs(cmd);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
CREATE INDEX IF NOT EXISTS idx_events_run ON run_events(run_id);

-- Insert default commands (will be updated with real profiles)
INSERT OR IGNORE INTO commands (cmd, profile_id, version, enabled, allowed_roles) VALUES
    ('@WORK', 'WORK_v1', 1, 1, '*'),
    ('@WRAP', 'WRAP_v1', 1, 1, '*'),
    ('@CLEAN', 'CLEAN_v1', 1, 1, '*'),
    ('@BUILD', 'BUILD_v1', 1, 1, '*'),
    ('@DEPLOY', 'DEPLOY_v1', 1, 1, 'admin,deployer');

-- Insert default client (for testing)
-- Secret: 'uasc-test-secret-change-me' -> SHA256
INSERT OR IGNORE INTO clients (client_id, client_name, secret_hash, roles, enabled) VALUES
    ('cli-local', 'Local CLI Client', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'admin', 1);
