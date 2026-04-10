-- UASC Executor Schema
-- SQLite database for command registry and audit logging

CREATE TABLE IF NOT EXISTS commands (
    cmd TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    allowed_roles TEXT DEFAULT '*',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    secret_hash TEXT NOT NULL,
    roles TEXT DEFAULT 'user',
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    cmd TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    client_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT DEFAULT (datetime('now')),
    ended_at TEXT,
    error TEXT,
    FOREIGN KEY (cmd) REFERENCES commands(cmd),
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_idx INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,
    ts TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_cmd ON runs(cmd);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
CREATE INDEX IF NOT EXISTS idx_events_run ON run_events(run_id);

-- Command registry: maps action types to execution profiles
INSERT OR IGNORE INTO commands (cmd, profile_id, version, enabled, allowed_roles) VALUES
    ('@WORK', 'WORK_v1', 1, 1, '*'),
    ('@WRAP', 'WRAP_v1', 1, 1, '*'),
    ('@CLEAN', 'CLEAN_v1', 1, 1, '*'),
    ('@BUILD', 'BUILD_v1', 1, 1, '*'),
    ('@DEPLOY', 'DEPLOY_v1', 1, 1, 'admin'),
    ('@CLOSE_LOOP', 'CLOSE_LOOP_v1', 1, 1, '*'),
    ('@SEND_DRAFT', 'SEND_DRAFT_v1', 1, 1, '*'),
    ('@BRIEF', 'BRIEF_v1', 1, 1, '*'),
    ('@EXECUTE', 'EXECUTE_v1', 1, 1, '*'),
    ('@SNAPSHOT', 'SNAPSHOT_v1', 1, 1, '*');

-- Delta-kernel is the primary client (shared secret for local IPC)
INSERT OR IGNORE INTO clients (client_id, client_name, secret_hash, roles, enabled) VALUES
    ('delta-kernel', 'Delta-Kernel Bridge', 'delta-kernel-local-secret', 'admin', 1),
    ('cli-local', 'Local CLI', 'cli-local-secret', 'admin', 1),
    ('atlas-execution-daemon', 'Atlas Execution Daemon', 'atlas-execution-daemon-local-secret', 'admin', 1);
