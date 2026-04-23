-- ============================================================
-- Restaurant Besteltool — Migration V4: RLS + Beveiliging
-- Voer dit uit na Migration V3
--
-- WAT DIT DOET:
--   1. leverancier_config verwijderen (vervangen door suppliers in V3)
--   2. RLS inschakelen op alle tabellen
--      → anon key heeft GEEN toegang meer
--      → app gebruikt service_role key die RLS omzeilt
--   3. Bestaande plaintext wachtwoorden hashen (bcrypt)
--   4. Login-functie aanmaken die veilig vergelijkt
--
-- BELANGRIJK: Vervang in Streamlit secrets de anon key door de
--   service_role key VOORDAT je deze migratie uitvoert.
--   Anders werkt de app niet meer.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. LEVERANCIER_CONFIG VERWIJDEREN
--    Vervangen door suppliers (V3). Code in db.py moet naar suppliers verwijzen.
DROP TABLE IF EXISTS leverancier_config;

-- 2. RLS INSCHAKELEN OP ALLE TABELLEN
ALTER TABLE sales_history          ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_count            ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast_log           ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants                ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_users           ENABLE ROW LEVEL SECURITY;
ALTER TABLE current_inventory      ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_adjustments  ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_usage            ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers              ENABLE ROW LEVEL SECURITY;

-- 3. WACHTWOORDEN HASHEN (eenmalig)
--    Slaat al-gehashte rijen over ($2a$ en $2b$ zijn bcrypt-prefixes)
UPDATE tenant_users
SET    password = crypt(password, gen_salt('bf'))
WHERE  password NOT LIKE '$2a$%'
  AND  password NOT LIKE '$2b$%';

-- 4. HULPFUNCTIE: wachtwoord hashen bij aanmaken gebruiker
--    pgcrypto (crypt, gen_salt) leeft in het 'extensions' schema in Supabase
CREATE OR REPLACE FUNCTION hash_password(p_password text)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT crypt(p_password, gen_salt('bf'));
$$;

-- 5. LOGIN FUNCTIE
--    Vergelijkt wachtwoord met bcrypt-hash zonder de hash bloot te stellen.
--    Voert altijd een hash-vergelijking uit (ook bij onbekende gebruiker)
--    zodat timing-attacks geen gebruikersnamen kunnen raden.
CREATE OR REPLACE FUNCTION verificeer_login(p_username text, p_password text)
RETURNS TABLE (
    tenant_id   uuid,
    tenant_naam text,
    username    text,
    role        text,
    full_name   text,
    permissions jsonb
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions, pg_temp
AS $$
DECLARE
    v_hash text;
BEGIN
    SELECT tu.password INTO v_hash
    FROM tenant_users tu
    WHERE tu.username = p_username
      AND tu.is_active = true;

    IF v_hash IS NULL THEN
        -- Altijd een bcrypt-vergelijking doen om timing-attacks te blokkeren
        PERFORM crypt(p_password, '$2a$10$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ012');
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        tu.tenant_id,
        t.name   AS tenant_naam,
        tu.username,
        tu.role,
        tu.full_name,
        tu.permissions
    FROM tenant_users tu
    JOIN tenants t ON t.id = tu.tenant_id
    WHERE tu.username = p_username
      AND tu.password = crypt(p_password, v_hash)
      AND tu.is_active = true
    LIMIT 1;
END;
$$;
