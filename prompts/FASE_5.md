# FASE 5 — FINANCIËLE FEEDBACK-LOOP
# Vereiste: Fase 2 (products met cost_price) + Fase 4 (recepten).
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
[F5.1] KOSTPRIJS + PRICE_HISTORY
──────────────────────────────────────────────────────────────
cost_price en cost_price_updated_at zijn al meegenomen in products-tabel (Fase 2).
Geen extra migratie op products nodig.

Nieuwe tabel (supabase_migration_v13_price_history.sql):
  CREATE TABLE price_history (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id),
    tenant_id  UUID NOT NULL REFERENCES tenants(id),
    old_price  NUMERIC(10,4),
    new_price  NUMERIC(10,4) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by TEXT NOT NULL
  );
  RLS policy op tenant_id.

Pas views/page_producten.py aan: voeg kostprijs-invoerveld toe.
Elke kostprijs-update via db.py logt automatisch een rij in price_history.

──────────────────────────────────────────────────────────────
[F5.2] VERSPILLINGS-DASHBOARD (views/page_verspilling.py)
──────────────────────────────────────────────────────────────
Databron: inventory_adjustments WHERE reason='verspilling' × products.cost_price
Toon: euro verspild per product, per week, trend over 4 weken.
Geen nieuwe tabel nodig.

──────────────────────────────────────────────────────────────
[F5.3] FOOD COST % DASHBOARD (views/page_food_cost.py)
──────────────────────────────────────────────────────────────
Databron: sales_history.revenue_eur (omzet) + inventory_adjustments × cost_price
Food cost % = (inkoopwaarde verbruikt / omzet) × 100
Toon als gauge + trendlijn (doel: <38%).

──────────────────────────────────────────────────────────────
[F5.4] BESPARINGSRAPPORT
──────────────────────────────────────────────────────────────
Combineer F5.2 + F5.3: "Als je verspilling met 20% verlaagt, bespaar je €X per maand."
Toon in views/page_food_cost.py als aparte sectie.
