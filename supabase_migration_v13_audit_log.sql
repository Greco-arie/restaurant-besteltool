-- ============================================================
-- Restaurant Besteltool — Migration V13: Audit Log
-- Voer uit na V12 (rls_jwt_policies)
--
-- WAT DIT DOET:
--   Maakt de audit_log tabel aan voor centrale traceability.
--   Elke relevante actie in de app wordt hier vastgelegd:
--     - login
--     - sluiting_opgeslagen
--     - bestelling_verzonden
--     - gebruiker_aangemaakt
--     - tenant_aangemaakt
--
--   RLS policy: managers/admins lezen alleen hun eigen tenant.
--   INSERT gaat via service_role vanuit de app (bypast RLS).
--
-- UITVOEREN:
--   Supabase Dashboard → SQL Editor → plakken → Run
-- ============================================================


-- ── Tabel ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  tenant_id    uuid        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_naam    text        NOT NULL,
  actie        text        NOT NULL,
  details      jsonb       DEFAULT '{}'::jsonb,
  created_at   timestamptz DEFAULT now()
);


-- ── Indexen ────────────────────────────────────────────────
-- Snelle opvraag van "laatste 7 dagen per tenant" (wekelijkse audit e-mail)
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created
  ON audit_log (tenant_id, created_at DESC);

-- Snel filteren op actiesoort (bijv. alleen logins tonen)
CREATE INDEX IF NOT EXISTS idx_audit_log_actie
  ON audit_log (actie);


-- ── Row Level Security ─────────────────────────────────────
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Lezen: alleen eigen tenant (via JWT-claim, conform V12-architectuur)
DROP POLICY IF EXISTS tenant_isolation_read ON audit_log;
CREATE POLICY tenant_isolation_read ON audit_log
  FOR SELECT TO authenticated
  USING (tenant_id = tenant_jwt_id());

-- Schrijven: alleen via service_role (bypast RLS automatisch).
-- Geen INSERT policy voor authenticated → app gebruikt get_client().


-- ── Verificatie ────────────────────────────────────────────
-- Controleer na uitvoeren:
SELECT tablename, policyname, cmd, roles
FROM   pg_policies
WHERE  tablename = 'audit_log'
ORDER  BY policyname;

SELECT indexname, indexdef
FROM   pg_indexes
WHERE  tablename = 'audit_log';
