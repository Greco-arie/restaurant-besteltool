-- ============================================================
-- Restaurant Besteltool — Migration V2: Multi-tenant + Inventaris
-- Voer dit EENMALIG uit in de Supabase SQL editor
-- ============================================================

-- Vereiste extensie voor wachtwoord-hashing (alvast laden voor de seed)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. TENANTS
CREATE TABLE IF NOT EXISTS tenants (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text        NOT NULL,
  slug       text        NOT NULL UNIQUE,
  status     text        NOT NULL DEFAULT 'active'
               CHECK (status IN ('active', 'inactive', 'suspended')),
  created_at timestamptz DEFAULT now()
);

-- 2. TENANT USERS
--    username is UNIQUE per tenant — twee tenants mogen allebei 'manager' hebben
CREATE TABLE IF NOT EXISTS tenant_users (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  username    text        NOT NULL,
  password    text        NOT NULL,
  role        text        NOT NULL DEFAULT 'manager'
                CHECK (role IN ('super_admin', 'admin', 'manager', 'user')),
  full_name   text        DEFAULT '',
  permissions jsonb       NOT NULL DEFAULT '{}',
  is_active   boolean     DEFAULT true,
  created_at  timestamptz DEFAULT now(),
  CONSTRAINT tenant_users_tenant_username_unique UNIQUE (tenant_id, username)
);

-- 3. TENANT_ID TOEVOEGEN AAN BESTAANDE TABELLEN
ALTER TABLE sales_history ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
ALTER TABLE stock_count   ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);
ALTER TABLE forecast_log  ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);

-- 4. LIVE VOORRAAD (huidige staat per tenant per SKU)
CREATE TABLE IF NOT EXISTS current_inventory (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id       uuid        NOT NULL REFERENCES tenants(id),
  sku_id          text        NOT NULL,
  current_stock   numeric(10,2) NOT NULL DEFAULT 0,
  unit            text        DEFAULT '',
  last_updated_at timestamptz DEFAULT now(),
  last_updated_by text        DEFAULT 'system',
  CONSTRAINT current_inventory_tenant_sku UNIQUE (tenant_id, sku_id)
);

-- 5. INVENTARIS CORRECTIES (audit trail)
CREATE TABLE IF NOT EXISTS inventory_adjustments (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id       uuid        NOT NULL REFERENCES tenants(id),
  sku_id          text        NOT NULL,
  adjustment_type text        NOT NULL,
  quantity_delta  numeric(10,2) NOT NULL,
  previous_stock  numeric(10,2) NOT NULL,
  new_stock       numeric(10,2) NOT NULL,
  reason          text        DEFAULT '',
  note            text        DEFAULT '',
  created_at      timestamptz DEFAULT now(),
  created_by      text        DEFAULT 'system'
);

-- 6. DAGELIJKS VERBRUIK (voor leermodel)
CREATE TABLE IF NOT EXISTS daily_usage (
  id                bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id         uuid        NOT NULL REFERENCES tenants(id),
  usage_date        date        NOT NULL,
  sku_id            text        NOT NULL,
  theoretical_usage numeric(10,2) NOT NULL DEFAULT 0,
  actual_covers     integer     NOT NULL DEFAULT 0,
  created_at        timestamptz DEFAULT now(),
  CONSTRAINT daily_usage_tenant_date_sku UNIQUE (tenant_id, usage_date, sku_id)
);

-- 7. RLS UITSCHAKELEN
--    De app gebruikt de service_role key die RLS omzeilt.
--    Migration V4 schakelt RLS in op alle tabellen.
ALTER TABLE tenants               DISABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_users          DISABLE ROW LEVEL SECURITY;
ALTER TABLE current_inventory     DISABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_adjustments DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_usage           DISABLE ROW LEVEL SECURITY;

-- 8. INDEXES OP FOREIGN KEYS
--    PostgreSQL maakt geen automatische index op FK-kolommen.
--    Zonder index: volledige tabelscan bij elke tenant-gefilterde query.
CREATE INDEX IF NOT EXISTS idx_sales_history_tenant     ON sales_history (tenant_id);
CREATE INDEX IF NOT EXISTS idx_stock_count_tenant       ON stock_count (tenant_id);
CREATE INDEX IF NOT EXISTS idx_forecast_log_tenant      ON forecast_log (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant      ON tenant_users (tenant_id);
CREATE INDEX IF NOT EXISTS idx_current_inventory_tenant ON current_inventory (tenant_id);
CREATE INDEX IF NOT EXISTS idx_inventory_adj_tenant     ON inventory_adjustments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_daily_usage_tenant       ON daily_usage (tenant_id);

-- 9. SEED: Family Maarssen tenant + gebruikers
--    Wachtwoorden direct gehasht met bcrypt — nooit plaintext opslaan
INSERT INTO tenants (id, name, slug)
VALUES ('11111111-1111-1111-1111-111111111111', 'Family Maarssen', 'family-maarssen')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO tenant_users (tenant_id, username, password, role, full_name)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'manager',
   crypt('family2024',  gen_salt('bf')), 'manager', 'Manager'),
  ('11111111-1111-1111-1111-111111111111', 'admin',
   crypt('besteltool!', gen_salt('bf')), 'admin',   'Admin')
ON CONFLICT (tenant_id, username) DO NOTHING;

-- 10. BACKFILL: bestaande data koppelen aan Family Maarssen
UPDATE sales_history SET tenant_id = '11111111-1111-1111-1111-111111111111' WHERE tenant_id IS NULL;
UPDATE stock_count   SET tenant_id = '11111111-1111-1111-1111-111111111111' WHERE tenant_id IS NULL;
UPDATE forecast_log  SET tenant_id = '11111111-1111-1111-1111-111111111111' WHERE tenant_id IS NULL;

-- 11. NOT NULL AFDWINGEN na backfill
--     Voorkomt dat nieuwe rijen zonder tenant worden ingevoegd (multi-tenancy lek)
ALTER TABLE sales_history ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE stock_count   ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE forecast_log  ALTER COLUMN tenant_id SET NOT NULL;
