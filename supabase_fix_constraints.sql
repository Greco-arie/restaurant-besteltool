-- ============================================================
-- Restaurant Besteltool — Fix: unique constraints naar multi-tenant
-- Voer dit EENMALIG uit in de Supabase SQL editor
-- ============================================================

-- 1. sales_history: was UNIQUE(date), moet UNIQUE(date, tenant_id)
alter table sales_history
  drop constraint if exists sales_history_date_unique;

alter table sales_history
  add constraint sales_history_date_tenant_unique unique (date, tenant_id);

-- 2. stock_count: was UNIQUE(date, sku_id), moet UNIQUE(date, sku_id, tenant_id)
alter table stock_count
  drop constraint if exists stock_count_date_sku_unique;

alter table stock_count
  add constraint stock_count_date_sku_tenant_unique unique (date, sku_id, tenant_id);

-- 3. forecast_log: was UNIQUE(datum), moet UNIQUE(datum, tenant_id)
alter table forecast_log
  drop constraint if exists forecast_log_datum_unique;

alter table forecast_log
  add constraint forecast_log_datum_tenant_unique unique (datum, tenant_id);

-- Klaar. Alle drie tabellen accepteren nu meerdere tenants per datum.

-- ============================================================
-- 4. Leverancier-configuratie per tenant (e-mailadressen etc.)
-- ============================================================
create table if not exists leverancier_config (
  id          bigint generated always as identity primary key,
  tenant_id   uuid not null references tenants(id) on delete cascade,
  leverancier text not null,
  email       text not null default '',
  aanhef      text not null default 'Beste leverancier,',
  updated_at  timestamptz default now(),
  constraint  leverancier_config_tenant_lev unique (tenant_id, leverancier)
);

alter table leverancier_config disable row level security;

-- Seed voor Family Maarssen
insert into leverancier_config (tenant_id, leverancier, email, aanhef)
values
  ('11111111-1111-1111-1111-111111111111', 'Hanos',             'inkoop@hanos.nl',           'Beste Hanos,'),
  ('11111111-1111-1111-1111-111111111111', 'Vers Leverancier',  'orders@versleverancier.nl', 'Beste leverancier,'),
  ('11111111-1111-1111-1111-111111111111', 'Bakkersland',       'orders@bakkersland.nl',     'Beste Bakkersland,'),
  ('11111111-1111-1111-1111-111111111111', 'Heineken Distrib.', 'orders@heineken.nl',        'Beste Heineken,')
on conflict (tenant_id, leverancier) do nothing;
