-- ============================================================
-- Restaurant Besteltool — Migration V3: Leveranciers + Rechten
-- Voer dit EENMALIG uit in de Supabase SQL editor
-- ============================================================

-- 1. SUPPLIERS tabel
--    Vervangt de hardcoded SUPPLIER_NAMEN en leverancier_config.
--    Elke tenant beheert zijn eigen leveranciers.
create table if not exists suppliers (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references tenants(id) on delete cascade,
  name            text not null,
  email           text default '',
  aanhef          text default 'Beste leverancier,',
  lead_time_days  integer not null default 1,

  -- Leverdagen per weekdag (True = levert op die dag)
  levert_ma       boolean not null default false,
  levert_di       boolean not null default false,
  levert_wo       boolean not null default false,
  levert_do       boolean not null default false,
  levert_vr       boolean not null default false,
  levert_za       boolean not null default false,
  levert_zo       boolean not null default false,

  is_active       boolean not null default true,
  created_at      timestamptz default now(),

  constraint suppliers_tenant_name unique (tenant_id, name)
);

-- 2. PERMISSIONS kolom op tenant_users
--    Alleen relevant voor de 'user' rol.
--    Opgeslagen als JSON: {"voorraad_wijzigen": true, "orders_versturen": false, ...}
alter table tenant_users
  add column if not exists permissions jsonb not null default '{}';

-- 3. RLS uitschakelen (consistent met rest van setup)
alter table suppliers disable row level security;

-- 4. SEED: Family Maarssen leveranciers
--    Leverdagen gebaseerd op standaard horeca leverpatronen.
insert into suppliers
  (tenant_id, name, email, aanhef, lead_time_days, levert_ma, levert_di, levert_wo, levert_do, levert_vr, levert_za, levert_zo)
values
  -- Hanos: bestellen op ma/wo, levering op di/do
  ('11111111-1111-1111-1111-111111111111',
   'Hanos',
   'inkoop@hanos.nl',
   'Beste Hanos,',
   1,
   false, true, false, true, false, false, false),

  -- Vers leverancier: levert di, do, za (vers = frequent)
  ('11111111-1111-1111-1111-111111111111',
   'Vers Leverancier',
   'orders@versleverancier.nl',
   'Beste leverancier,',
   1,
   false, true, false, true, false, true, false),

  -- Bakkersland: levert ma, wo, vr
  ('11111111-1111-1111-1111-111111111111',
   'Bakkersland',
   'orders@bakkersland.nl',
   'Beste Bakkersland,',
   1,
   true, false, true, false, true, false, false),

  -- Heineken Distributie: 1x per week, op di (levertijd 2 dagen)
  ('11111111-1111-1111-1111-111111111111',
   'Heineken Distrib.',
   'orders@heineken.nl',
   'Beste Heineken,',
   2,
   false, true, false, false, false, false, false)

on conflict (tenant_id, name) do nothing;
