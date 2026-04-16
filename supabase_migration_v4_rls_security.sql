-- ============================================================
-- Restaurant Besteltool — Migration V4: RLS Beveiliging
-- Voer dit uit in de Supabase SQL editor
--
-- WAT DIT DOET:
--   1. RLS inschakelen op alle tabellen (anon key krijgt NULRECHTEN)
--   2. De app gebruikt voortaan de service_role key die RLS omzeilt
--   3. Wachtwoorden worden gehasht opgeslagen (bcrypt)
--
-- BELANGRIJK: Voer stap 1 uit NADAT je in de app secrets
--   "key" hebt vervangen door de service_role key.
--   Anders werkt de app niet meer.
-- ============================================================

-- 1. RLS INSCHAKELEN OP ALLE TABELLEN
--    Met RLS aan maar zonder policies: anon key heeft GEEN toegang.
--    De service_role key bypass RLS standaard — de app blijft werken.

ALTER TABLE sales_history          ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_count            ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast_log           ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants                ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_users           ENABLE ROW LEVEL SECURITY;
ALTER TABLE current_inventory      ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_adjustments  ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_usage            ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers              ENABLE ROW LEVEL SECURITY;

-- 2. VERIFIEER: geen publieke policies aanwezig
--    (Als je ooit policies hebt aangemaakt, drop ze hier)
--    Voorbeeld: DROP POLICY IF EXISTS "public_read" ON sales_history;

-- 3. WACHTWOORD HASHING — STAP 3a: pgcrypto extensie aanzetten
--    (staat standaard al aan in Supabase)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 3b. Bestaande plaintext wachtwoorden hashen
--    VOER DIT EENMALIG UIT — daarna werkt de app met gehashte wachtwoorden
UPDATE tenant_users
SET    password = crypt(password, gen_salt('bf'))
WHERE  password NOT LIKE '$2a$%'   -- sla al-gehashte rijen over
  AND  password NOT LIKE '$2b$%';

-- 4. HULPFUNCTIE — hash een nieuw wachtwoord (gebruikt bij aanmaken gebruiker)
CREATE OR REPLACE FUNCTION hash_password(p_password text)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT crypt(p_password, gen_salt('bf'));
$$;

-- 5. LOGIN FUNCTIE — vergelijkt wachtwoord met bcrypt hash
--    De app roept deze aan via rpc('verificeer_login', ...)
--    Zo hoeven wachtwoord-hashes NOOIT de database te verlaten.
CREATE OR REPLACE FUNCTION verificeer_login(p_username text, p_password text)
RETURNS TABLE (
    tenant_id   uuid,
    tenant_naam text,
    username    text,
    role        text,
    full_name   text,
    permissions jsonb
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        tu.tenant_id,
        t.name   AS tenant_naam,
        tu.username,
        tu.role,
        tu.full_name,
        tu.permissions
    FROM tenant_users tu
    JOIN tenants t ON t.id = tu.tenant_id
    WHERE tu.username  = p_username
      AND tu.password  = crypt(p_password, tu.password)
      AND tu.is_active = true
    LIMIT 1;
$$;

-- ============================================================
-- NA DEZE MIGRATIE:
--   - Secrets bijwerken: zie README of secrets.toml
--   - App opnieuw deployen op Streamlit Cloud
-- ============================================================
