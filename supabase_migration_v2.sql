-- ============================================================
-- Restaurant Besteltool — Migration V2: Multi-tenant + Inventaris
-- Voer dit EENMALIG uit in de Supabase SQL editor
-- ============================================================

-- 1. TENANTS
create table if not exists tenants (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  slug       text not null unique,
  status     text not null default 'active',
  created_at timestamptz default now()
);

-- 2. TENANT USERS
create table if not exists tenant_users (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references tenants(id) on delete cascade,
  username   text not null unique,
  password   text not null,
  role       text not null default 'manager',
  full_name  text default '',
  is_active  boolean default true,
  created_at timestamptz default now()
);

-- 3. TENANT_ID TOEVOEGEN AAN BESTAANDE TABELLEN
alter table sales_history add column if not exists tenant_id uuid references tenants(id);
alter table stock_count   add column if not exists tenant_id uuid references tenants(id);
alter table forecast_log  add column if not exists tenant_id uuid references tenants(id);

-- 4. LIVE VOORRAAD (huidige staat per tenant per SKU)
create table if not exists current_inventory (
  id              bigint generated always as identity primary key,
  tenant_id       uuid not null references tenants(id),
  sku_id          text not null,
  current_stock   numeric(10,2) not null default 0,
  unit            text default '',
  last_updated_at timestamptz default now(),
  last_updated_by text default 'system',
  constraint      current_inventory_tenant_sku unique (tenant_id, sku_id)
);

-- 5. INVENTARIS CORRECTIES (audit trail)
create table if not exists inventory_adjustments (
  id               bigint generated always as identity primary key,
  tenant_id        uuid not null references tenants(id),
  sku_id           text not null,
  adjustment_type  text not null,
  quantity_delta   numeric(10,2) not null,
  previous_stock   numeric(10,2) not null,
  new_stock        numeric(10,2) not null,
  reason           text default '',
  note             text default '',
  created_at       timestamptz default now(),
  created_by       text default 'system'
);

-- 6. DAGELIJKS VERBRUIK (voor leermodel)
create table if not exists daily_usage (
  id                bigint generated always as identity primary key,
  tenant_id         uuid not null references tenants(id),
  usage_date        date not null,
  sku_id            text not null,
  theoretical_usage numeric(10,3) not null default 0,
  actual_covers     integer not null default 0,
  created_at        timestamptz default now(),
  constraint        daily_usage_tenant_date_sku unique (tenant_id, usage_date, sku_id)
);

-- 7. RLS UITSCHAKELEN (simpele setup voor V2)
alter table tenants               disable row level security;
alter table tenant_users          disable row level security;
alter table current_inventory     disable row level security;
alter table inventory_adjustments disable row level security;
alter table daily_usage           disable row level security;

-- 8. SEED: Family Maarssen tenant + gebruikers
insert into tenants (id, name, slug)
values ('11111111-1111-1111-1111-111111111111', 'Family Maarssen', 'family-maarssen')
on conflict (slug) do nothing;

insert into tenant_users (tenant_id, username, password, role, full_name)
values
  ('11111111-1111-1111-1111-111111111111', 'manager', 'family2024',  'manager', 'Manager'),
  ('11111111-1111-1111-1111-111111111111', 'admin',   'besteltool!', 'admin',   'Admin')
on conflict (username) do nothing;

-- 9. BACKFILL bestaande data naar Family Maarssen tenant
update sales_history set tenant_id = '11111111-1111-1111-1111-111111111111' where tenant_id is null;
update stock_count   set tenant_id = '11111111-1111-1111-1111-111111111111' where tenant_id is null;
update forecast_log  set tenant_id = '11111111-1111-1111-1111-111111111111' where tenant_id is null;
