# Restaurant Besteltool V2 — Master Implementation Prompt
# Versie 3.0 · April 2026

================================================================
HOE TE GEBRUIKEN
================================================================
Kopieer dit volledige document in een nieuw gesprek.
Claude werkt fase voor fase. Elke fase begint pas na een expliciete ✅ van jou.
Claude stopt na elke fase en vraagt bevestiging voordat hij verdergaat.

================================================================
ROL
================================================================
Senior full-stack engineer. Productiegericht: lever pas op als iets aantoonbaar werkt.
Spreek Nederlands naar de manager, Engels in code en commits.

NIET HERBOUWEN — controleer altijd eerst of het al bestaat:
  email_service.py   → verzend_bestelling(), _genereer_pdf()        [DONE]
  monitoring.py      → log_event(), log_error(), stel_sentry_context_in() [DONE]
  forecast.py        → bereken_forecast() + alle sub-functies
  recommendation.py  → bereken_alle_adviezen(), groepeer_per_leverancier()
  inventory.py       → laad_huidige_voorraad(), sla_sluitstock_op()
  learning.py        → bereken_correctiefactor(), laad_accuracy_overzicht()
  db.py              → get_client(), laad_leveranciers_dict()
  models.py          → WeatherData, ForecastResult, UserSession, Product
Importeer en extend. Nooit opnieuw schrijven.

================================================================
CONTEXT
================================================================
Stack:   Python 3.13 · Streamlit (live, Streamlit Cloud) · FastAPI (toe te bouwen)
DB:      Supabase PostgreSQL · service_role client bypasses RLS
Auth:    eigen bcrypt · RPC verificeer_login(p_tenant_slug, p_username, p_password)
         rollen: user < manager < admin < super_admin
Tabellen: tenants · tenant_users · suppliers · sales_history · stock_count ·
          forecast_log · current_inventory · inventory_adjustments · daily_usage
⚠ Geen products-tabel in Supabase — zit in demo_data/products.csv

Forecast:     baseline × trend × reservering × covers × correctie × terras
Besteladvies: max(0, vraag_per_cover × covers × days − voorraad + buffer) → afgerond op pack_qty

Toe te voegen lagen:
  FastAPI (naast Streamlit, apart port) · Celery+Redis of GitHub Actions · HTML dashboard

================================================================
STOP CONDITIONS (gelden voor elke feature)
================================================================
Af = ALLE punten groen:
  1. Migratie toegepast op testtenant
  2. Cross-tenant pytest FAALT correct
  3. ≥1 happy-path test + ≥1 edge-case test, beide gelogd
  4. UI handmatig doorlopen (of: "wacht op rooktest door Aris")
  5. FastAPI endpoint: live curl-test gelogd (indien van toepassing)
  6. Manager-handleiding max 10 regels NL geschreven

Niet af bij: "zou moeten werken" / code zonder uitgevoerde test.
Bij blocker: STOP — meld exact wat, waarom, wat Aris moet doen, wat daarna.

================================================================
OUTPUT FORMAT
================================================================
### [Fcode]: [naam]
**Risico opgelost:** · **Geraakt:** · **Nieuw:** · **Migratie:**
**Code:** [volledige code] · **Test:** [pytest + uitvoer] · **Live-verificatie:**
**Manager-handleiding:** [max 10 regels NL] · **Status:** gevalideerd/geblokkeerd


================================================================
══════════════════════════════════════════════════════════════
FASE 1 — PRODUCTIE-FUNDAMENT (blocker eerste klant)
══════════════════════════════════════════════════════════════
================================================================

[F1.1] SENT_EMAILS TABEL
  email_service.py is DONE — raak verzend_bestelling() NIET aan.
  (a) Migratie: CREATE TABLE sent_emails (id UUID PK, tenant_id UUID REFS tenants,
      supplier_id UUID REFS suppliers, supplier_naam TEXT, bestel_datum DATE,
      resend_id TEXT, status TEXT DEFAULT 'sent', timestamp TIMESTAMPTZ DEFAULT NOW());
      RLS policy op tenant_id.
  (b) views/page_export.py: insert rij in sent_emails na elke succesvolle verzending.
  (c) app.py: controleer bij start of RESEND_API_KEY aanwezig is; log via monitoring.

[F1.2] SENTRY VERIFICATIE
  monitoring.py is DONE — raak dit bestand NIET aan.
  (a) Verifieer SENTRY_DSN in productie-secrets; documenteer stap voor Aris indien ontbreekt.
  (b) views/page_admin.py: voeg verborgen "Sentry test"-knop toe (super_admin only).
  (c) app.py: verifieer dat stel_sentry_context_in() aanroepen bij elke paginawissel.

[F1.3] DAGELIJKSE BACKUP
  Kies én documenteer: GitHub Actions (aanbevolen) of Celery (als Redis al loopt).
  GitHub Actions (.github/workflows/backup.yml · cron 03:00 UTC):
    pg_dump → GPG-encrypt (.sql.gz) → Backblaze B2 → verwijder >30 dagen oud.
  Lever SECRETS_CHECKLIST.md met exacte secrets die Aris moet aanmaken.
  Lever restore-instructies als commentaar in backup.yml.

⏸ FASE 1 GATE
Controleer alle stop conditions. Rapporteer:
  ✅/❌ sent_emails tabel + page_export.py getest
  ✅/❌ Sentry verificatie + testknop
  ✅/❌ Backup workflow actief + restore gedocumenteerd
Wacht op "ga verder" van Aris voordat FASE 2 start.


================================================================
══════════════════════════════════════════════════════════════
FASE 2 — DATALAAG-CONSOLIDATIE (vóór klant #2)
══════════════════════════════════════════════════════════════
================================================================

[F2.1] PRODUCTS CSV → SUPABASE
  Bron: demo_data/products.csv (sku_id, sku_name, base_unit, pack_qty,
        demand_per_cover, min_stock, supplier_type)
  Nieuwe tabel products (migratie v9): id UUID PK, tenant_id UUID NOT NULL,
    sku_id TEXT, naam TEXT, eenheid TEXT, verpakkingseenheid NUMERIC,
    vraag_per_cover NUMERIC, minimumvoorraad NUMERIC DEFAULT 0,
    buffer_pct NUMERIC DEFAULT 0.15, supplier_id UUID REFS suppliers,
    cost_price NUMERIC(10,4), is_actief BOOLEAN DEFAULT TRUE,
    UNIQUE(tenant_id, sku_id). RLS op tenant_id.
  Schrijf migrate_products.py: lees CSV → match supplier_type → upsert →
    diff-rapport (nieuw/gewijzigd/ongewijzigd) · --dry-run · --tenant-slug vlaggen.

[F2.2] CSV-CODEPADEN VERWIJDEREN
  data_loader.load_products() → vervang door db.laad_producten(tenant_id).
  load_events() + load_reservations() → NIET verwijderen (geen Supabase-equivalent).
  _load_stock_count_csv() → verwijder CSV-fallback; toon duidelijke foutmelding bij lege DB.
  Pas aan: views/page_producten.py + recommendation.py.

⏸ FASE 2 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 3 — SECURITY-HARDENING
══════════════════════════════════════════════════════════════
================================================================

[F3.1] ECHTE RLS VIA JWT
  Probleem: service_role bypassed RLS altijd (Supabase API-niveau).
  Oplossing: tenant-operaties via anon_key + JWT met tenant_id claim.

  Aris voegt toe aan Streamlit secrets:
    [supabase]
    anon_key   = "..."    # Supabase → Settings → API → anon public
    jwt_secret = "..."    # Supabase → Settings → API → JWT Secret

  SQL: ENABLE ROW LEVEL SECURITY op alle 8 tenant-tabellen + tenants-tabel.
    Policies tenant-tabellen: USING (tenant_id::text = auth.jwt() ->> 'tenant_id')
    tenants-tabel:            USING ((auth.jwt() ->> 'app_role') = 'super_admin')

  db.py toevoegen:
    _maak_tenant_jwt(tenant_id, app_role='authenticated') → JWT via PyJWT
    get_tenant_client(tenant_id) → anon client met JWT-header (RLS actief)
    get_admin_client() → service_role (alleen cross-tenant super_admin operaties)
  Hernoem alle tenant-functies van get_client() naar get_tenant_client(tenant_id).

  tests/test_rls.py: query met JWT van tenant A op data van tenant B → MOET leeg.
  docs/rls-policies.md: documenteer elke policy.

[F3.2] 2FA VIA TOTP (NIET via Supabase Auth MFA)
  SQL migratie: ALTER TABLE tenant_users ADD COLUMN mfa_secret TEXT,
                ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;
  views/setup_2fa_page.py:
    (a) pyotp.random_base32() → QR-code → st.image()
    (b) pyotp.TOTP(secret).verify(code)
    (c) Sla mfa_secret + mfa_enabled=TRUE op via db.py
  app.py login-flow: na wachtwoord-check → als mfa_enabled: TOTP-stap.
  Managers (>= manager) zonder 2FA → geforceerde setup bij eerste login.

⏸ FASE 3 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 4 — RECEPTENBEHEER (manager en hoger)
══════════════════════════════════════════════════════════════
================================================================

Vereiste: Fase 2 (products-tabel in Supabase) klaar.
Probleem: vraag_per_cover raakt verouderd bij portiewijziging.
Oplossing: recepten koppelen aan producten; wijziging herberekent automatisch.

[F4.1] DATABASE (migratie v12)
  recipes: id UUID PK, tenant_id UUID REFS tenants, naam TEXT,
           selling_price NUMERIC(10,2), is_actief BOOLEAN DEFAULT TRUE.
  recipe_ingredients: id UUID PK, recipe_id UUID REFS recipes ON DELETE CASCADE,
           product_id UUID REFS products, quantity_per_serving NUMERIC, unit TEXT,
           UNIQUE(recipe_id, product_id). RLS via recipes.tenant_id.

[F4.2] LOGICA (db.py uitbreiden)
  laad_recepten(tenant_id) · sla_recept_op(tenant_id, data, ingrediënten)
  herbereken_vraag_per_cover(tenant_id, product_id):
    Som quantity_per_serving over actieve recepten → schrijf naar products.vraag_per_cover
    Log in inventory_adjustments: reason='recept_wijziging', note=f"portie {oud}→{nieuw}"
    Invalideer st.cache_data voor producten.

[F4.3] UI (views/page_recepten.py — nieuw)
  Sectie 1: receptenlijst (naam, prijs, aantal ingrediënten, actief)
  Sectie 2: toevoegen/bewerken (formulier + ingrediënten-editor per regel)
  Sectie 3: impact-preview VOOR opslaan: "vraag_per_cover van X gaat van 0.08 → 0.11"
             Manager bevestigt expliciet → dan pas opslaan + herberekening.
  Voeg "Recepten" toe aan navigatie in app.py voor rollen >= manager.
  models.py: class Recipe + class RecipeIngredient (frozen=True).

⏸ FASE 4 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 5 — FINANCIËLE FEEDBACK-LOOP
══════════════════════════════════════════════════════════════
================================================================

Vereiste: Fase 2 (products met cost_price) + Fase 4 (recepten) klaar.

[F5.1] KOSTPRIJS + PRICE_HISTORY
  cost_price + cost_price_updated_at al in products-tabel (Fase 2) — geen extra migratie.
  Nieuwe tabel price_history (migratie v13): product_id, tenant_id, old_price,
    new_price, changed_at, changed_by. RLS op tenant_id.
  views/page_producten.py: kostprijs-invoerveld; elke wijziging logt naar price_history.

[F5.2] VERSPILLINGS-DASHBOARD (views/page_verspilling.py)
  Bron: inventory_adjustments WHERE reason='verspilling' × products.cost_price.
  Toon: euro verspild per product per week, trend 4 weken. Geen nieuwe tabel.

[F5.3] FOOD COST % DASHBOARD (views/page_food_cost.py)
  Food cost % = (inkoopwaarde verbruikt / sales_history.revenue_eur) × 100.
  Toon als gauge + trendlijn. Doel: <38%.
  Besparingsrapport: "−20% verspilling = €X/maand besparing."

⏸ FASE 5 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 6 — FORECAST VERDIEPING
══════════════════════════════════════════════════════════════
================================================================

[F6.1] FEESTDAGEN ALS FACTOR
  Plug IN bereken_forecast() als extra factor: ... × correctie × terras × holiday_factor.
  Tabel holiday_multipliers (migratie v14): tenant_id, holiday_name, multiplier.
  Seed NL defaults: Koningsdag 1.6, Kerstavond 1.4, Nieuwjaarsdag 0.3, etc.
  pip install holidays (NL kalender). Manager past multipliers aan in page_instellingen.py.

[F6.2] P10/P50/P90 BANDBREEDTE
  Extend ForecastResult (frozen) met p10, p50, p90.
  std_dev per weekdag uit laatste 8 datapunten. P10 = mean−1.28×std · P90 = mean+1.28×std.
  Fallback ±15% bij <4 datapunten. Toon als bereik-balk in page_forecast.py.

[F6.3] MAPE DASHBOARD UITBOUWEN
  page_leerrapport.py bestaat als stub — UITBOUWEN.
  Importeer learning.laad_accuracy_overzicht() — NIET herbouwen.
  Voeg toe: MAPE per weekdag · rollend 8-weken venster · groen<10%/geel10–20%/rood>20%.

⏸ FASE 6 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 7 — FASTAPI REST API
══════════════════════════════════════════════════════════════
================================================================

FastAPI draait NAAST Streamlit (apart process, apart port). Streamlit blijft intact.
Nieuwe map api/ in project root.

[F7.1] api/dependencies.py
  get_supabase_client() · get_tenant_id() uit Bearer header · rate limit 100 req/min (slowapi)

[F7.2] ENDPOINTS
  GET  /dashboard/summary → {today, low_stock_alerts, forecast_tomorrow, weekly_revenue}
       Cache 5 min (fastapi-cache2)
  GET  /analytics/sales?period=week|month|quarter
  GET  /analytics/products  (top/bottom 10)
  GET  /analytics/forecast-vs-actual?weeks=8  → wrap learning.laad_accuracy_overzicht()
  GET  /inventory/status
  POST /orders/generate  → importeer recommendation.bereken_alle_adviezen()
  GET  /orders/history   → uit sent_emails
  GET/POST/PATCH /recipes · DELETE /recipes/{id}/ingredients/{pid}
       → gebruik herbereken_vraag_per_cover() uit db.py

[F7.3] SERVICES (api/services/)
  analytics_service.py: top_producten · omzet_trend · food_cost_pct · verspilling_euro
  insights_engine.py:   best sellers · slow movers · forecast-afwijking per weekdag
  Alle responses < 200ms. Index op (tenant_id, date).

⏸ FASE 7 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 8 — ANALYTICS DASHBOARD
══════════════════════════════════════════════════════════════
================================================================

Vereiste: Fase 7 live. Read-only voor eigenaar/investeerder. Geen Streamlit.
Tech: HTML + Tailwind CSS CDN + Chart.js CDN. Geserveerd door FastAPI als static files.

dashboard/index.html:
  KPI-kaarten: omzet vandaag · bonnen · lage-voorraad alerts (rood/groen)
  Grafieken: omzet 7 dagen (lijn) · top 10 producten (staaf) · forecast vs. werkelijk (groep)
  Knoppen: "Besteladvies genereren" → POST /orders/generate · "Exporteer CSV"
  Responsive (tablet) · auto-refresh 5 min · authenticatie via Bearer token in localStorage

dashboard/static/app.js:
  fetchSummary() · renderKPIs() · renderCharts() · handleOrderGenerate()
  Fetch API only — geen framework.

⏸ FASE 8 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 9 — ACHTERGRONDTAKEN
══════════════════════════════════════════════════════════════
================================================================

Kies en documenteer: GitHub Actions (aanbevolen) of Celery (als Redis al loopt).

Dagelijkse forecast herberekening (22:00): alle actieve tenants, opslaan in forecast_log.
  Importeer bereken_forecast() — NIET herbouwen.
Dagelijkse analytics update (06:00): herbereken aggregaties voor gisteren → cache.
Dagelijkse backup (03:00): zie F1.3 — als GitHub Actions al klaar: overslaan.

SQL migratie v15: ALTER TABLE tenants ADD COLUMN low_stock_alert_pct NUMERIC DEFAULT 0.20,
                  ADD COLUMN food_cost_alert_pct NUMERIC DEFAULT 0.38;

⏸ FASE 9 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 10 — ORDER-ENGINE VERDIEPING
══════════════════════════════════════════════════════════════
================================================================

Vereiste: Fase 2 (products-tabel) klaar.

[F10.1] MOQ + GRATIS-BEZORGINGSDREMPEL
  SQL v16: ALTER TABLE suppliers ADD COLUMN min_order_value NUMERIC(10,2),
           ADD COLUMN free_delivery_threshold NUMERIC(10,2).
  page_instellingen.py: velden toevoegen (leveranciersbeheer bestaat al).
  page_review.py: suggestie "Je zit op €180 bij Hanos. Bestel €20 extra voor gratis bezorging."

[F10.2] HOUDBAARHEID ALS BESTELBOVENGRENS
  SQL: ALTER TABLE products ADD COLUMN shelf_life_days INTEGER.
  recommendation.py: max_order = vraag_per_cover × covers × shelf_life_days.
  Als besteladvies > max_order: cap + waarschuwing tonen.

[F10.3] FIFO-BATCHES MET VERLOOPALERT
  SQL v18: stock_batches (product_id, tenant_id, purchase_date, expiry_date,
           initial_quantity, current_quantity, status). RLS op tenant_id.
  inventory.py: bij verbruik oudste batch eerst (FIFO).
  page_inventaris.py: nieuwe batch bij levering. Alert bij <3 dagen tot verloopdatum.

⏸ FASE 10 GATE — wacht op "ga verder" van Aris.


================================================================
══════════════════════════════════════════════════════════════
FASE 11 — UX + ONBOARDING
══════════════════════════════════════════════════════════════
================================================================

Vereiste: Fase 2 klaar.

[F11.1] TABLET-GEOPTIMALISEERDE REVIEW-PAGINA
  Pas views/page_review.py aan — NIET herbouwen. Houd CSS (#2E5AAC).
  Voeg toe: grote knoppen (≥48×48px) · +/− per product · accordeon per leverancier.

[F11.2] STARTERSCATALOGI + VOORGEDEFINIEERDE LEVERANCIERS
  SQL: tabel starter_catalogs (kitchen_type TEXT, product_template JSONB).
  Seed: 30–50 producten per type (italiaans/aziatisch/bistro/brasserie/grill/cafe).
  Seed leveranciers: Hanos, Sligro, Bidfood, Makro, Lekkerland + standaard leverdagen.
  page_instellingen.py: keuzentype + leveranciers kiezen bij onboarding.

[F11.3] EXCEL/CSV-IMPORT WIZARD
  Sectie toevoegen aan views/page_producten.py (bestaande pagina).
  Upload .xlsx (openpyxl) of .csv → kolom-mapping → preview 10 rijen →
  import met duplicate-detectie op (tenant_id, sku_id) →
  rapport: X geïmporteerd · Y gewijzigd · Z overgeslagen.

⏸ FASE 11 GATE — KLAAR
Alle fases voltooid. Rapporteer eindstatus per fase.
