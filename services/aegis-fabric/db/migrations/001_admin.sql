-- Aegis Delta Fabric — Admin Database Schema
-- Applied to the aegis_admin database on first boot.
-- Stores the master tenant registry and cross-tenant admin audit trail.

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    tier            TEXT NOT NULL DEFAULT 'FREE' CHECK (tier IN ('FREE', 'STARTER', 'ENTERPRISE')),
    mode            TEXT NOT NULL DEFAULT 'BUILD' CHECK (mode IN ('RECOVER', 'CLOSURE', 'MAINTENANCE', 'BUILD', 'COMPOUND', 'SCALE')),
    quotas          JSONB NOT NULL DEFAULT '{
        "max_agents": 2,
        "max_actions_per_hour": 100,
        "max_entities": 500,
        "max_delta_log_size": 5000,
        "max_webhook_count": 2
    }'::jsonb,
    api_key_hash    TEXT NOT NULL,
    db_name         TEXT NOT NULL UNIQUE,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    isolation_model TEXT NOT NULL DEFAULT 'SILOED' CHECK (isolation_model IN ('SILOED', 'POOLED')),
    capabilities    TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_api_key_hash ON tenants (api_key_hash);
CREATE INDEX IF NOT EXISTS idx_tenants_enabled ON tenants (enabled);

CREATE TABLE IF NOT EXISTS global_audit (
    audit_id    TEXT PRIMARY KEY,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_global_audit_created_at ON global_audit (created_at DESC);
