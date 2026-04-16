-- ============================================================
-- Restaurant Besteltool — Migration V5: Super Admin rol
-- Voer uit in Supabase SQL Editor
-- ============================================================

-- 1. Super Admin account aanmaken
--    Vervang 'KIES_EEN_STERK_WACHTWOORD' door jouw wachtwoord.
--    Voer dit uit, log daarna in als 'superadmin'.

INSERT INTO tenant_users (tenant_id, username, password, role, full_name, is_active)
SELECT
    id,
    'superadmin',
    crypt('KIES_EEN_STERK_WACHTWOORD', gen_salt('bf')),
    'super_admin',
    'Super Admin',
    true
FROM tenants
WHERE slug = 'family-maarssen'
ON CONFLICT (username) DO NOTHING;

-- 2. Verifieer: super_admin staat er in
SELECT username, role, full_name FROM tenant_users WHERE role = 'super_admin';
