# FASE 2 — DATALAAG-CONSOLIDATIE
# Vereiste: Fase 1 klaar. Vóór klant #2.
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
[F2.1] PRODUCTS-TABEL MIGREREN VANUIT CSV
──────────────────────────────────────────────────────────────
Bron: demo_data/products.csv
Kolommen: sku_id, sku_name, base_unit, pack_qty, demand_per_cover, min_stock, supplier_type
supplier_type waarden: "wholesale" / "fresh" / "bakery" / "beer"

Nieuwe tabel (supabase_migration_v9_products.sql):
  products (
    id UUID PK, tenant_id UUID NOT NULL REFS tenants,
    sku_id TEXT NOT NULL, naam TEXT NOT NULL, eenheid TEXT NOT NULL,
    verpakkingseenheid NUMERIC NOT NULL, vraag_per_cover NUMERIC NOT NULL,
    minimumvoorraad NUMERIC NOT NULL DEFAULT 0, buffer_pct NUMERIC NOT NULL DEFAULT 0.15,
    supplier_id UUID REFS suppliers, cost_price NUMERIC(10,4),
    cost_price_updated_at TIMESTAMPTZ, is_actief BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, sku_id)
  )
  RLS policy op tenant_id.

Schrijf migrate_products.py (project root):
(a) Lees demo_data/products.csv
(b) Match supplier_type → supplier_id via db.laad_leveranciers_dict(tenant_id)
(c) Upsert op (tenant_id, sku_id) — idempotent
(d) Print diff-rapport: nieuw / gewijzigd / ongewijzigd
(e) Vlag --dry-run · Vlag --tenant-slug

──────────────────────────────────────────────────────────────
[F2.2] CSV-CODEPADEN VERWIJDEREN
──────────────────────────────────────────────────────────────
In data_loader.py:
  - load_products() → vervangen door db.laad_producten(tenant_id)
  - load_events() en load_reservations() → NIET verwijderen (geen Supabase-equivalent)
  - _load_stock_count_csv() → verwijder CSV-fallback; bij lege DB duidelijke foutmelding

Pas aan: views/page_producten.py + recommendation.py (laad via db.laad_producten)

Voeg toe in app.py:
  import os
  assert not os.path.exists('demo_data/products.csv') or os.getenv('ALLOW_CSV') == '1', \
         'products.csv must be migrated to Supabase'
  (zet ALLOW_CSV=1 in secrets.toml tijdens migratierun zelf)
