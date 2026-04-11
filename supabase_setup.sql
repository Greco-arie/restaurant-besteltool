-- ============================================================
-- Restaurant Besteltool — Database setup
-- Voer dit eenmalig uit in de Supabase SQL editor
-- ============================================================

-- Dagelijkse omzet en bonnen (closing data)
create table if not exists sales_history (
  id          bigint generated always as identity primary key,
  date        date not null,
  weekday     text,
  covers      integer not null default 0,
  revenue_eur numeric(10,2) not null default 0,
  note        text default '',
  constraint  sales_history_date_unique unique (date)
);

-- Voorraadtellingen per dag per SKU
create table if not exists stock_count (
  id          bigint generated always as identity primary key,
  date        date not null,
  sku_id      text not null,
  on_hand_qty numeric(10,2) not null default 0,
  unit        text default '',
  note        text default '',
  constraint  stock_count_date_sku_unique unique (date, sku_id)
);

-- Forecast log — groeit dagelijks, basis voor leermodel
create table if not exists forecast_log (
  id               bigint generated always as identity primary key,
  datum            date not null,
  weekdag          integer,
  event_naam       text default 'geen event',
  predicted_covers numeric(10,1),
  actual_covers    numeric(10,1),
  omzet_werkelijk  numeric(10,2),
  notitie          text default '',
  constraint       forecast_log_datum_unique unique (datum)
);

-- Toegang voor de app via de publishable key
alter table sales_history disable row level security;
alter table stock_count   disable row level security;
alter table forecast_log  disable row level security;
