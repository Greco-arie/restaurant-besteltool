-- ============================================================
-- Restaurant Besteltool — Migration V2.1: Constraints multi-tenant
-- Voer dit EENMALIG uit na Migration V2
-- ============================================================

-- 1. sales_history: UNIQUE(date) → UNIQUE(date, tenant_id)
ALTER TABLE sales_history
  DROP CONSTRAINT IF EXISTS sales_history_date_unique;
ALTER TABLE sales_history
  ADD CONSTRAINT sales_history_date_tenant_unique UNIQUE (date, tenant_id);

-- 2. stock_count: UNIQUE(date, sku_id) → UNIQUE(date, sku_id, tenant_id)
ALTER TABLE stock_count
  DROP CONSTRAINT IF EXISTS stock_count_date_sku_unique;
ALTER TABLE stock_count
  ADD CONSTRAINT stock_count_date_sku_tenant_unique UNIQUE (date, sku_id, tenant_id);

-- 3. forecast_log: UNIQUE(datum) → UNIQUE(datum, tenant_id)
ALTER TABLE forecast_log
  DROP CONSTRAINT IF EXISTS forecast_log_datum_unique;
ALTER TABLE forecast_log
  ADD CONSTRAINT forecast_log_datum_tenant_unique UNIQUE (datum, tenant_id);

-- 4. tenant_users: username was globaal UNIQUE — moet per tenant zijn
--    Zonder deze fix: tweede klant kan geen 'manager' aanmaken want die bestaat al
ALTER TABLE tenant_users
  DROP CONSTRAINT IF EXISTS tenant_users_username_key;
ALTER TABLE tenant_users
  DROP CONSTRAINT IF EXISTS tenant_users_tenant_username_unique;
ALTER TABLE tenant_users
  ADD CONSTRAINT tenant_users_tenant_username_unique UNIQUE (tenant_id, username);
