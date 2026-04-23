-- ============================================================
-- Restaurant Besteltool — Migration V9: sent_emails tabel
-- Voer uit na V8.
--
-- WAT DIT DOET:
--   Bijhoudt elke verzonden bestelling per leverancier per dag.
--   Geeft managers en super_admin inzicht in verzendhistorie
--   zonder afhankelijkheid van Resend-dashboard.
--
-- GEBRUIK:
--   Kopieer en plak in Supabase SQL Editor → Run.
-- ============================================================

CREATE TABLE IF NOT EXISTS sent_emails (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL REFERENCES tenants(id)    ON DELETE CASCADE,
    supplier_id   UUID                  REFERENCES suppliers(id)  ON DELETE SET NULL,
    supplier_naam TEXT         NOT NULL,
    bestel_datum  DATE         NOT NULL,
    resend_id     TEXT,
    status        TEXT         NOT NULL DEFAULT 'sent',
    timestamp     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index voor snelle tenant-queries (verzendhistorie per klant)
CREATE INDEX IF NOT EXISTS idx_sent_emails_tenant_datum
    ON sent_emails (tenant_id, bestel_datum DESC);

-- RLS: elke tenant ziet alleen zijn eigen verzendingen
ALTER TABLE sent_emails ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolatie_sent_emails"
    ON sent_emails
    FOR ALL
    USING (
        tenant_id::text = (auth.jwt() ->> 'tenant_id')
        OR (auth.jwt() ->> 'app_role') = 'super_admin'
    );

-- service_role (huidige app) bypassed RLS automatisch —
-- bovenstaande policy is al klaar voor Fase 3 (JWT-auth).
