-- Migration v11: password reset tokens + email kolom op tenant_users
-- Voer uit in Supabase SQL Editor (Dashboard → SQL Editor → New query)

-- Stap 1: email kolom toevoegen aan tenant_users (nullable)
ALTER TABLE tenant_users ADD COLUMN IF NOT EXISTS email TEXT;

-- Stap 2: password_reset_tokens tabel aanmaken
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     UUID        NOT NULL REFERENCES tenant_users(id) ON DELETE CASCADE,
    token_hash  TEXT        NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index voor snelle token-lookup (primair gebruik: verificatie op hash)
CREATE INDEX IF NOT EXISTS idx_reset_tokens_hash   ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_user   ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_expiry ON password_reset_tokens(expires_at);

-- RLS: tokens zijn niet zichtbaar via de anon/authenticated rol (alleen service_role)
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
