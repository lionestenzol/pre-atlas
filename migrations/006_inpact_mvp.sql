-- Migration 006: inPACT cloud sync + entitlements
-- Backs SPEC_MVP_36H.md blocks B-F (apps/inpact/).
--
-- app_state stores the exact CycleBoardState.state shape as one JSONB blob per
-- user (see apps/inpact/js/state.js:getDefaultState). No column-per-field —
-- normalize later only if there's a real reporting need (spec section 11).
--
-- entitlements is written ONLY by the Stripe webhook edge function using the
-- service role, which bypasses RLS. The browser client has read-only access so
-- it can render gated UI but can never grant itself Pro. Free tier is the
-- built-in default: a user with no row is free.
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS app_state (
    user_id    UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    state      JSONB NOT NULL,
    version    TEXT NOT NULL DEFAULT '2.0',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE app_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "own state" ON app_state;
CREATE POLICY "own state" ON app_state
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS entitlements (
    user_id             UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    tier                TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro')),
    status              TEXT NOT NULL DEFAULT 'inactive',
    stripe_customer_id  TEXT,
    current_period_end  TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE entitlements ENABLE ROW LEVEL SECURITY;

-- Read-only for the owner. No INSERT/UPDATE/DELETE policy exists for the
-- anon/authenticated roles, so only the service-role key (used by the Stripe
-- webhook function) can write here — it bypasses RLS entirely.
DROP POLICY IF EXISTS "own entitlement read" ON entitlements;
CREATE POLICY "own entitlement read" ON entitlements
    FOR SELECT
    USING (auth.uid() = user_id);

-- Keep updated_at honest on every write, for both tables.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS app_state_set_updated_at ON app_state;
CREATE TRIGGER app_state_set_updated_at
    BEFORE UPDATE ON app_state
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS entitlements_set_updated_at ON entitlements;
CREATE TRIGGER entitlements_set_updated_at
    BEFORE UPDATE ON entitlements
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
