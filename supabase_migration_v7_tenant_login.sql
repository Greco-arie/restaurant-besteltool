-- ============================================================
-- Restaurant Besteltool — Migration V7: Tenant-scoped login
-- Voer uit na V6 cleanup.
--
-- Probleem (HIGH-1 uit SQL audit V6):
--   De oude verificeer_login(p_username, p_password) zocht alleen op username.
--   Omdat V2 (tenant_id, username) UNIQUE maakt, kan dezelfde username in
--   meerdere tenants bestaan. De oude functie kon dan de verkeerde tenant
--   teruggeven bij toevallige username-collisies.
--
-- Oplossing:
--   verificeer_login eist nu tenant_slug als extra parameter. Lookup
--   wordt gescoped op (tenants.slug, tenant_users.username).
--
-- Impact:
--   - db.verificeer_gebruiker() moet nu tenant_slug meesturen (gedaan in Python)
--   - De loginpagina vraagt nu 'Restaurant' (default 'family-maarssen')
--
-- Security design notes:
--   - `status = 'active'` is de enige login-toegelaten status. 'inactive'
--     en 'suspended' blokkeren login zonder onderscheid — intentioneel,
--     zodat aanvallers geen tenant-enumeratie kunnen doen via foutmeldingen.
--   - Timing-attack bescherming: bcrypt wordt altijd als eerste uitgevoerd,
--     ongeacht of tenant/user bestaat. Zo verschilt de responstijd niet
--     zichtbaar tussen "user bestaat niet" en "wachtwoord fout".
--   - Er blijft een klein timing-verschil tussen "tenant bestaat niet"
--     (1 DB-roundtrip) en "tenant bestaat" (2 roundtrips). Acceptabel voor
--     single-tenant deployment; bij multi-tenant met verborgen slugs moet
--     dit overgaan naar een enkele LEFT JOIN-query.
--   - GRANT EXECUTE: service_role in Supabase kan van nature alle functies
--     uitvoeren; de Python-app gebruikt service_role, dus geen expliciete
--     GRANT nodig. Bij overgang naar anon-rol moet dit expliciet gegrant.
-- ============================================================

BEGIN;

-- 1. DROP oude functie (kwetsbare 2-param signature)
DROP FUNCTION IF EXISTS verificeer_login(text, text);

-- 2. CREATE nieuwe functie met tenant_slug als eerste parameter
CREATE OR REPLACE FUNCTION verificeer_login(
    p_tenant_slug text,
    p_username    text,
    p_password    text
)
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
    v_tenant_id uuid;
    v_hash      text;
    v_dummy     text;
BEGIN
    -- Stap 0: ALTIJD bcrypt uitvoeren als eerste handeling.
    -- Dit blokkeert timing-zijkanalen tussen "tenant bestaat niet",
    -- "user bestaat niet" en "wachtwoord fout" — alle drie de paden
    -- bevatten minstens één crypt()-call met dezelfde work-factor.
    v_dummy := crypt(p_password, '$2a$10$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ012');

    -- Stap 1: tenant lookup via slug (alleen actieve tenants)
    SELECT id INTO v_tenant_id
    FROM tenants
    WHERE slug   = p_tenant_slug
      AND status = 'active';

    IF v_tenant_id IS NULL THEN
        RETURN;  -- tenant bestaat niet of is niet actief
    END IF;

    -- Stap 2: user lookup binnen deze tenant
    SELECT tu.password INTO v_hash
    FROM tenant_users tu
    WHERE tu.tenant_id = v_tenant_id
      AND tu.username  = p_username
      AND tu.is_active = true;

    IF v_hash IS NULL THEN
        RETURN;  -- user bestaat niet binnen deze tenant
    END IF;

    -- Stap 3: password verify + row teruggeven
    -- NB: JOIN op tenants herhaalt status='active' om een race condition te
    -- voorkomen waarbij de tenant tussen stap 1 en stap 3 ge-deactiveerd wordt.
    RETURN QUERY
    SELECT
        tu.tenant_id,
        t.name   AS tenant_naam,
        tu.username,
        tu.role,
        tu.full_name,
        tu.permissions
    FROM tenant_users tu
    JOIN tenants t
      ON t.id     = tu.tenant_id
     AND t.status = 'active'
    WHERE tu.tenant_id = v_tenant_id
      AND tu.username  = p_username
      AND tu.password  = crypt(p_password, v_hash)
      AND tu.is_active = true
    LIMIT 1;
END;
$$;

COMMIT;

-- ============================================================
-- VERIFICATIE — draai deze apart, NA de commit hierboven
-- ============================================================

-- A. De functie bestaat met 3 parameters
SELECT
    proname                        AS function_name,
    pg_get_function_arguments(oid) AS args,
    pg_get_function_result(oid)    AS returns
FROM pg_proc
WHERE proname = 'verificeer_login';
-- Verwacht: 1 rij, args = 'p_tenant_slug text, p_username text, p_password text'

-- B. De oude 2-param versie is weg
SELECT COUNT(*) AS oude_functies_aanwezig
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE p.proname = 'verificeer_login'
  AND pg_get_function_arguments(p.oid) = 'p_username text, p_password text';
-- Verwacht: 0

-- C. SMOKE TEST — vervang JOUW_WACHTWOORD door het echte superadmin wachtwoord
--    VOORDAT je deze query draait. Een lege set met de placeholder betekent
--    "wachtwoord klopt niet", niet "V7 werkt niet".
SELECT * FROM verificeer_login('family-maarssen', 'superadmin', 'JOUW_WACHTWOORD');
-- Verwacht (met correct wachtwoord): 1 rij met role = 'super_admin'

-- D. NEGATIVE TEST — verkeerde tenant_slug moet 0 rijen geven
SELECT * FROM verificeer_login('bestaat-niet', 'superadmin', 'JOUW_WACHTWOORD');
-- Verwacht: 0 rijen

-- E. NEGATIVE TEST — juiste tenant, niet-bestaande user
SELECT * FROM verificeer_login('family-maarssen', 'bestaat-niet', 'wachtwoord');
-- Verwacht: 0 rijen
