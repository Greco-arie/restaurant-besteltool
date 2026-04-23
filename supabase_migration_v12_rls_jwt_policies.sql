-- ============================================================
-- Restaurant Besteltool — Migration V12: RLS JWT Policies
-- Voer uit na V11 (password_reset)
--
-- WAT DIT DOET:
--   RLS policies aanmaken voor de 'authenticated' role.
--   De app signt nu een JWT met tenant_id-claim en stuurt die
--   mee als Authorization-header. Deze policies controleren
--   of tenant_id in de JWT overeenkomt met de rij-tenant_id.
--
--   service_role bypast RLS altijd — admin-functies in db.py
--   (laad_alle_tenants, maak_gebruiker_aan, etc.) blijven werken.
--
-- UITVOEREN:
--   Supabase Dashboard → SQL Editor → plakken → Run
-- ============================================================


-- ── Hulpfunctie: haal tenant_id uit JWT-claim ──────────────
-- Gebruik in policies: tenant_jwt_id() = rij.tenant_id
CREATE OR REPLACE FUNCTION tenant_jwt_id()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
  SELECT (auth.jwt() ->> 'tenant_id')::uuid;
$$;


-- ── suppliers ──────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON suppliers;
CREATE POLICY tenant_isolation ON suppliers
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── products ───────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON products;
CREATE POLICY tenant_isolation ON products
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── sent_emails ────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON sent_emails;
CREATE POLICY tenant_isolation ON sent_emails
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── sales_history ──────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON sales_history;
CREATE POLICY tenant_isolation ON sales_history
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── stock_count ────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON stock_count;
CREATE POLICY tenant_isolation ON stock_count
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── forecast_log ───────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON forecast_log;
CREATE POLICY tenant_isolation ON forecast_log
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── current_inventory ──────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON current_inventory;
CREATE POLICY tenant_isolation ON current_inventory
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── inventory_adjustments ──────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON inventory_adjustments;
CREATE POLICY tenant_isolation ON inventory_adjustments
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── daily_usage ────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON daily_usage;
CREATE POLICY tenant_isolation ON daily_usage
  FOR ALL TO authenticated
  USING      (tenant_id = tenant_jwt_id())
  WITH CHECK (tenant_id = tenant_jwt_id());


-- ── Verificatie query ──────────────────────────────────────
-- Controleer na uitvoeren of alle policies bestaan:
SELECT schemaname, tablename, policyname, roles, cmd
FROM   pg_policies
WHERE  policyname = 'tenant_isolation'
ORDER  BY tablename;
