# FASE 10 — ORDER-ENGINE VERDIEPING
# Vereiste: Fase 2 (products-tabel). Fase 7 aanbevolen.
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
[F10.1] MOQ + GRATIS-BEZORGINGSDREMPEL
──────────────────────────────────────────────────────────────
SQL (supabase_migration_v16_moq.sql):
  ALTER TABLE suppliers
    ADD COLUMN min_order_value        NUMERIC(10,2),
    ADD COLUMN free_delivery_threshold NUMERIC(10,2);

Pas views/page_instellingen.py aan (leveranciersbeheer bestaat al).
Voeg suggestie toe in views/page_review.py:
  "Je zit op €180 bij Hanos. Bestel voor €20 extra voor gratis bezorging."
  Aanbevolen product: hoogste rotatie + langste houdbaarheid.

──────────────────────────────────────────────────────────────
[F10.2] HOUDBAARHEID ALS BESTELBOVENGRENS
──────────────────────────────────────────────────────────────
Voeg kolom toe aan products (migratie toevoegen aan v9 of aparte v17):
  ALTER TABLE products ADD COLUMN shelf_life_days INTEGER;

In recommendation.py bereken_alle_adviezen():
  max_order = vraag_per_cover × forecast_covers × shelf_life_days
  Als besteladvies > max_order: cap op max_order + toon waarschuwing

──────────────────────────────────────────────────────────────
[F10.3] FIFO-BATCHES MET VERLOOPALERT
──────────────────────────────────────────────────────────────
SQL (supabase_migration_v18_batches.sql):
  CREATE TABLE stock_batches (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id       UUID NOT NULL REFERENCES products(id),
    tenant_id        UUID NOT NULL REFERENCES tenants(id),
    purchase_date    DATE NOT NULL,
    expiry_date      DATE,
    initial_quantity NUMERIC NOT NULL,
    current_quantity NUMERIC NOT NULL,
    status           TEXT NOT NULL DEFAULT 'actief'  -- actief/verlopen/recalled
  );
  RLS policy op tenant_id.

Logica in inventory.py:
  Bij levering: nieuwe batch aanmaken via views/page_inventaris.py
  Bij verbruik: oudste batch eerst afboeken (FIFO)

Alert: welke batches verlopen in <3 dagen? Toon op inventarispagina.
Dagelijkse check via workers/tasks (Fase 9) of Streamlit at_start.
