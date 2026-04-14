-- Aegis Delta Fabric — Per-Tenant Database Schema
-- Applied to each new tenant database (e.g., aegis_tnt_001) when a tenant is created.
-- All tables are tenant-scoped — no tenant_id column needed (database-level isolation).

-- Delta Log: append-only, hash-chained
CREATE TABLE IF NOT EXISTS deltas (
    delta_id    BIGSERIAL PRIMARY KEY,
    hash        TEXT NOT NULL UNIQUE,
    hash_prev   TEXT,
    patch       JSONB NOT NULL,
    author_type TEXT NOT NULL CHECK (author_type IN ('agent', 'human', 'system', 'policy-engine')),
    author_id   TEXT NOT NULL,
    entity_id   TEXT,
    meta        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deltas_hash_prev ON deltas (hash_prev);
CREATE INDEX IF NOT EXISTS idx_deltas_created_at ON deltas (created_at);
CREATE INDEX IF NOT EXISTS idx_deltas_entity_id ON deltas (entity_id);

-- Entities: current materialized state
CREATE TABLE IF NOT EXISTS entities (
    entity_id   TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    current_hash TEXT NOT NULL,
    state       JSONB NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities (entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_archived ON entities (is_archived) WHERE is_archived = false;

-- Snapshots: periodic full-state captures for fast replay
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    delta_id    BIGINT NOT NULL REFERENCES deltas(delta_id),
    state_hash  TEXT NOT NULL,
    state       JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_delta_id ON snapshots (delta_id);

-- Agents: registered LLM agent instances
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    provider        TEXT NOT NULL CHECK (provider IN ('claude', 'openai', 'local', 'custom')),
    version         TEXT NOT NULL DEFAULT '1.0.0',
    capabilities    TEXT[] NOT NULL DEFAULT '{}',
    cost_center     TEXT NOT NULL DEFAULT 'default',
    enabled         BOOLEAN NOT NULL DEFAULT true,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Policies: versioned rule sets
CREATE TABLE IF NOT EXISTS policies (
    policy_id   TEXT PRIMARY KEY,
    version     INTEGER NOT NULL DEFAULT 1,
    rules       JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Approvals: human-in-the-loop queue
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    action_id   TEXT NOT NULL,
    agent_id    TEXT NOT NULL,
    action      TEXT NOT NULL,
    params      JSONB NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at  TIMESTAMPTZ,
    decided_by  TEXT,
    reason      TEXT,
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals (status);
CREATE INDEX IF NOT EXISTS idx_approvals_expires ON approvals (expires_at) WHERE status = 'PENDING';

-- Webhooks: event notification endpoints
CREATE TABLE IF NOT EXISTS webhooks (
    webhook_id      TEXT PRIMARY KEY,
    url             TEXT NOT NULL,
    events          TEXT[] NOT NULL DEFAULT '{}',
    secret_hash     TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    retry_count     INTEGER NOT NULL DEFAULT 3,
    failure_count   INTEGER NOT NULL DEFAULT 0,
    last_triggered_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit Log: append-only trail of all actions
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id    TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    action      TEXT NOT NULL,
    effect      TEXT NOT NULL CHECK (effect IN ('ALLOW', 'DENY', 'REQUIRE_HUMAN')),
    entity_ids  TEXT[] DEFAULT '{}',
    delta_id    BIGINT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_log (agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action);

-- Idempotency Keys: prevent duplicate action processing
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key         TEXT PRIMARY KEY,
    response    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys (expires_at);

-- Usage Records: per-agent, per-period cost tracking
CREATE TABLE IF NOT EXISTS usage_records (
    agent_id        TEXT NOT NULL,
    period          TEXT NOT NULL,
    actions_count   INTEGER NOT NULL DEFAULT 0,
    tokens_used     INTEGER NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,6) NOT NULL DEFAULT 0,
    by_action       JSONB DEFAULT '{}',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, period)
);
