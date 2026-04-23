-- ============================================================
-- Restaurant Besteltool — Migration V6: Cleanup / hardening
-- Brengt de bestaande database in lijn met de schone schema-definitie.
-- Idempotent: veilig om meerdere keren uit te voeren.
-- ============================================================

-- 1. CHECK CONSTRAINTS op status en role (ontbraken in V2)
DO $$ BEGIN
  ALTER TABLE tenants
    ADD CONSTRAINT tenants_status_check
    CHECK (status IN ('active', 'inactive', 'suspended'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE tenant_users
    ADD CONSTRAINT tenant_users_role_check
    CHECK (role IN ('super_admin', 'admin', 'manager', 'user'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 2. BACKFILL + NOT NULL op tenant_id (multi-tenancy lek voorkomen)
UPDATE sales_history SET tenant_id = '11111111-1111-1111-1111-111111111111' WHERE tenant_id IS NULL;
UPDATE stock_count   SET tenant_id = '11111111-1111-1111-1111-111111111111' WHERE tenant_id IS NULL;
UPDATE forecast_log  SET tenant_id = '11111111-1111-1111-1111-111111111111' WHERE tenant_id IS NULL;

ALTER TABLE sales_history ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE stock_count   ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE forecast_log  ALTER COLUMN tenant_id SET NOT NULL;

-- 3. USERNAME UNIQUE per tenant (was globaal)
ALTER TABLE tenant_users DROP CONSTRAINT IF EXISTS tenant_users_username_key;
ALTER TABLE tenant_users DROP CONSTRAINT IF EXISTS tenant_users_tenant_username_unique;
ALTER TABLE tenant_users
  ADD CONSTRAINT tenant_users_tenant_username_unique UNIQUE (tenant_id, username);

-- 4. INDEXES OP FOREIGN KEYS (performance)
CREATE INDEX IF NOT EXISTS idx_sales_history_tenant     ON sales_history (tenant_id);
CREATE INDEX IF NOT EXISTS idx_stock_count_tenant       ON stock_count (tenant_id);
CREATE INDEX IF NOT EXISTS idx_forecast_log_tenant      ON forecast_log (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant      ON tenant_users (tenant_id);
CREATE INDEX IF NOT EXISTS idx_current_inventory_tenant ON current_inventory (tenant_id);
CREATE INDEX IF NOT EXISTS idx_inventory_adj_tenant     ON inventory_adjustments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_daily_usage_tenant       ON daily_usage (tenant_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_tenant         ON suppliers (tenant_id);

-- 5. LEVERANCIER_CONFIG OPRUIMEN (vervangen door suppliers in V3)
DROP TABLE IF EXISTS leverancier_config;

-- 6. SECURITY DEFINER FUNCTIES — search_path fix + timing-attack bescherming
--    pgcrypto (crypt, gen_salt) leeft in het 'extensions' schema in Supabase
CREATE OR REPLACE FUNCTION hash_password(p_password text)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT crypt(p_password, gen_salt('bf'));
$$;

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
        -- Altijd een bcrypt-vergelijking uitvoeren → timing attacks geblokkeerd
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

-- 7. VERIFICATIE
SELECT 'tenants CHECK'      AS check_name, pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'tenants_status_check'
UNION ALL
SELECT 'tenant_users CHECK', pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'tenant_users_role_check'
UNION ALL
SELECT 'username UNIQUE',    pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'tenant_users_tenant_username_unique';
