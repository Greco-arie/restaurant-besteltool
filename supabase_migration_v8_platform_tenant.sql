-- ============================================================
-- Restaurant Besteltool — Migration V8: Platform tenant + superadmin isolatie
-- Voer uit na V7.
--
-- Probleem:
--   In V5 is de `superadmin` account aangemaakt binnen de klant-tenant
--   `family-maarssen`. Dat betekent dat de platform-eigenaar (jij) in
--   dezelfde tenant zit als het horeca-personeel van die klant:
--     - Verwarrend vanuit data-isolatie oogpunt
--     - Als family-maarssen ooit op status=inactive gezet wordt,
--       is de superadmin per ongeluk ook geblokkeerd
--     - Een SQL-fout bij klant-deletion kan per ongeluk superadmin raken
--
-- Oplossing:
--   1. Een aparte `platform` tenant aanmaken die geen klant is
--   2. De superadmin verhuizen van family-maarssen naar platform
--   3. Geen data-tabellen aan platform koppelen (suppliers/sales/stock blijven
--      per-klant)
--
-- Na V8 logt superadmin in met:
--     Restaurant: platform
--     Gebruiker:  superadmin
--     Wachtwoord: (bestaand, niet gewijzigd)
--
-- Impact Python app:
--   Geen code-wijzigingen nodig — verificeer_login is tenant-slug-agnostisch,
--   werkt met elke slug die bestaat in tenants. De default in de login-form
--   blijft 'family-maarssen' voor gewoon personeel; superadmin typt 'platform'.
--
-- Design notes:
--   - Vast UUID voor platform (`22222222-...`) zodat reproduceerbaar + makkelijk
--     te herkennen in logs (family-maarssen = `11111111-...`).
--   - ON CONFLICT DO NOTHING bij tenant-insert → idempotent (veilig herdraaien).
--   - UPDATE is tenant-scoped op username='superadmin' met role='super_admin'
--     als extra veiligheid zodat geen andere rij per ongeluk verhuist.
--   - Verificatie check E onderaan controleert dat login met nieuwe slug werkt.
-- ============================================================

BEGIN;

-- 1. Platform tenant aanmaken (idempotent)
INSERT INTO tenants (id, name, slug, status)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    'Platform',
    'platform',
    'active'
)
ON CONFLICT (id) DO NOTHING;

-- 2. Superadmin verhuizen van family-maarssen → platform
--    Scoped op username + role zodat geen andere rij per ongeluk verhuist.
UPDATE tenant_users
SET tenant_id = '22222222-2222-2222-2222-222222222222'
WHERE username = 'superadmin'
  AND role     = 'super_admin'
  AND tenant_id = (SELECT id FROM tenants WHERE slug = 'family-maarssen');

COMMIT;

-- ============================================================
-- VERIFICATIE — draai deze apart, NA de commit hierboven
-- ============================================================

-- A. Platform tenant bestaat
SELECT id, name, slug, status
FROM tenants
WHERE slug = 'platform';
-- Verwacht: 1 rij met status='active'

-- B. Superadmin staat in platform (NIET meer in family-maarssen)
SELECT tu.username, tu.role, t.slug AS tenant_slug, t.name AS tenant_naam
FROM tenant_users tu
JOIN tenants t ON t.id = tu.tenant_id
WHERE tu.role = 'super_admin';
-- Verwacht: 1 rij met tenant_slug='platform'

-- C. Family-maarssen heeft géén super_admin meer
SELECT COUNT(*) AS oude_superadmin_in_family
FROM tenant_users tu
JOIN tenants t ON t.id = tu.tenant_id
WHERE tu.role = 'super_admin'
  AND t.slug  = 'family-maarssen';
-- Verwacht: 0

-- D. Family-maarssen heeft nog steeds z'n eigen normale users (manager etc.)
SELECT username, role
FROM tenant_users tu
JOIN tenants t ON t.id = tu.tenant_id
WHERE t.slug = 'family-maarssen'
ORDER BY role, username;
-- Verwacht: manager/admin/user rijen, géén super_admin

-- E. SMOKE TEST — login met platform moet werken
--    Vervang 'besteltool!' door het échte superadmin-wachtwoord als dat afwijkt.
SELECT tenant_id, username, role, full_name
FROM verificeer_login('platform', 'superadmin', 'besteltool!');
-- Verwacht: 1 rij met role='super_admin', tenant_id=22222222-...

-- F. NEGATIVE TEST — login met oude slug moet 0 rijen geven
SELECT COUNT(*) AS oude_login_werkt_nog
FROM verificeer_login('family-maarssen', 'superadmin', 'besteltool!');
-- Verwacht: 0 (superadmin zit er niet meer in)
