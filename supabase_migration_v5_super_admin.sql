-- ============================================================
-- Restaurant Besteltool — Migration V5: Super Admin
-- Voer uit na Migration V4
--
-- Vervang 'KIES_EEN_STERK_WACHTWOORD' door jouw wachtwoord.
-- ============================================================

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
ON CONFLICT (tenant_id, username) DO NOTHING;

-- Verificatie: super_admin staat er in
SELECT username, role, full_name FROM tenant_users WHERE role = 'super_admin';
