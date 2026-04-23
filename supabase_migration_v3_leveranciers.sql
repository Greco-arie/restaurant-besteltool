-- ============================================================
-- Restaurant Besteltool — Migration V3: Leveranciers + Rechten
-- Voer dit EENMALIG uit na Migration V2.1
-- ============================================================

-- 1. SUPPLIERS tabel
--    Volledige vervanging van leverancier_config: bevat leverdagen en levertijd.
--    leverancier_config wordt verwijderd in Migration V4.
CREATE TABLE IF NOT EXISTS suppliers (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name           text        NOT NULL,
  email          text        DEFAULT '',
  aanhef         text        DEFAULT 'Beste leverancier,',
  lead_time_days integer     NOT NULL DEFAULT 1,

  -- Leverdagen per weekdag
  levert_ma      boolean     NOT NULL DEFAULT false,
  levert_di      boolean     NOT NULL DEFAULT false,
  levert_wo      boolean     NOT NULL DEFAULT false,
  levert_do      boolean     NOT NULL DEFAULT false,
  levert_vr      boolean     NOT NULL DEFAULT false,
  levert_za      boolean     NOT NULL DEFAULT false,
  levert_zo      boolean     NOT NULL DEFAULT false,

  is_active      boolean     NOT NULL DEFAULT true,
  created_at     timestamptz DEFAULT now(),

  CONSTRAINT suppliers_tenant_name UNIQUE (tenant_id, name)
);

ALTER TABLE suppliers DISABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_suppliers_tenant ON suppliers (tenant_id);

-- 2. PERMISSIONS kolom op tenant_users
--    {"voorraad_wijzigen": true, "orders_versturen": false, ...}
--    IF NOT EXISTS: veilig om opnieuw uit te voeren als V2 al permissions had
ALTER TABLE tenant_users
  ADD COLUMN IF NOT EXISTS permissions jsonb NOT NULL DEFAULT '{}';

-- 3. SEED: Family Maarssen leveranciers
INSERT INTO suppliers
  (tenant_id, name, email, aanhef, lead_time_days,
   levert_ma, levert_di, levert_wo, levert_do, levert_vr, levert_za, levert_zo)
VALUES
  -- Hanos: levert di en do
  ('11111111-1111-1111-1111-111111111111',
   'Hanos', 'inkoop@hanos.nl', 'Beste Hanos,', 1,
   false, true, false, true, false, false, false),

  -- Vers Leverancier: levert di, do, za
  ('11111111-1111-1111-1111-111111111111',
   'Vers Leverancier', 'orders@versleverancier.nl', 'Beste leverancier,', 1,
   false, true, false, true, false, true, false),

  -- Bakkersland: levert ma, wo, vr
  ('11111111-1111-1111-1111-111111111111',
   'Bakkersland', 'orders@bakkersland.nl', 'Beste Bakkersland,', 1,
   true, false, true, false, true, false, false),

  -- Heineken Distributie: 1x per week op di, levertijd 2 dagen
  ('11111111-1111-1111-1111-111111111111',
   'Heineken Distrib.', 'orders@heineken.nl', 'Beste Heineken,', 2,
   false, true, false, false, false, false, false)

ON CONFLICT (tenant_id, name) DO NOTHING;
