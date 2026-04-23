# FASE 7 — FASTAPI REST API
# Vereiste: Fase 2 (products-tabel) aanbevolen. Fase 3 (RLS) aanbevolen.
# FastAPI draait NAAST Streamlit — apart process, apart port. Streamlit blijft intact.
# Plak dit samen met BASE_CONTEXT.md.

Nieuwe mapstructuur (toevoegen aan project root):
  api/
    main.py          FastAPI app, CORS, lifespan, static files mount
    dependencies.py  get_supabase_client(), get_tenant_id() uit Bearer header, rate limit
    routers/
      dashboard.py   GET /dashboard/summary
      analytics.py   GET /analytics/sales · /products · /forecast-vs-actual
      inventory.py   GET /inventory/status
      orders.py      POST /orders/generate · GET /orders/history
      recipes.py     GET/POST/PATCH /recipes · DELETE /recipes/{id}/ingredients/{pid}
    services/
      analytics_service.py  aggregaties (zie hieronder)
      insights_engine.py    best sellers, slow movers, trends

──────────────────────────────────────────────────────────────
[F7.1] DEPENDENCIES (api/dependencies.py)
──────────────────────────────────────────────────────────────
get_supabase_client() → service_role client (zelfde patroon als db.py)
get_tenant_id()       → lees tenant slug uit Authorization: Bearer <slug> header
                        lookup tenant_id uit tenants-tabel op slug
Rate limiting: max 100 req/min per tenant (slowapi)

──────────────────────────────────────────────────────────────
[F7.2] ENDPOINTS
──────────────────────────────────────────────────────────────
GET /dashboard/summary → {
  today: {revenue, covers, date},
  low_stock_alerts: [{sku_id, naam, current, minimum}],
  forecast_tomorrow: {covers, confidence},
  weekly_revenue: [{date, revenue}]   // 7 dagen
}
Cache: 5 minuten (fastapi-cache2 in-memory of Redis)

GET /analytics/sales?period=week|month|quarter
GET /analytics/products       (top 10 + bottom 10)
GET /analytics/forecast-vs-actual?weeks=8
  NIET herbouwen: importeer learning.laad_accuracy_overzicht() en wrap

GET /inventory/status          → current_inventory joined met products
POST /orders/generate          → importeer recommendation.bereken_alle_adviezen()
GET  /orders/history           → uit sent_emails tabel

GET    /recipes
POST   /recipes                (manager en hoger)
PATCH  /recipes/{id}           (manager en hoger)
DELETE /recipes/{id}/ingredients/{product_id}
  Gebruik herbereken_vraag_per_cover() uit db.py

──────────────────────────────────────────────────────────────
[F7.3] SERVICES
──────────────────────────────────────────────────────────────
analytics_service.py:
  bereken_top_producten(tenant_id, period) → list[dict]
  bereken_omzet_trend(tenant_id, period)   → list[dict]
  bereken_food_cost_pct(tenant_id, period) → float
  bereken_verspilling_euro(tenant_id, period) → float

insights_engine.py:
  genereer_inzichten(tenant_id) → list[dict]
  Best sellers, slow movers, forecast-afwijking per weekdag, omzettrend

Alle responses < 200ms. Index op (tenant_id, date) voor alle relevante tabellen.
