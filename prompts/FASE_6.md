# FASE 6 — FORECAST VERDIEPING
# Vereiste: geen (uitbreiden bestaande forecast.py).
# Raak bereken_forecast() NIET aan zonder de formule intact te houden.
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
[F6.1] FEESTDAGEN ALS FACTOR IN BEREKEN_FORECAST()
──────────────────────────────────────────────────────────────
PLUG IN — NIET naast de berekening, maar ALS extra factor:
  ... × correctie_factor × terras_factor × holiday_factor

SQL (supabase_migration_v14_holidays.sql):
  CREATE TABLE holiday_multipliers (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    holiday_name TEXT NOT NULL,
    multiplier   NUMERIC NOT NULL DEFAULT 1.0,
    UNIQUE(tenant_id, holiday_name)
  );
  RLS policy op tenant_id.
  Seed NL defaults: Koningsdag 1.6, Kerstavond 1.4, Nieuwjaarsdag 0.3,
                    Paaszondag 1.3, Hemelvaartsdag 1.2, Pinksteren 1.2.

Implementatie forecast.py:
  from holidays import NL  # pip install holidays
  holiday_factor = db.laad_holiday_multiplier(tenant_id, datum) of 1.0

Toon actieve feestdag in ForecastResult.drivers.
Manager kan multipliers aanpassen in views/page_instellingen.py (nieuwe sectie).

──────────────────────────────────────────────────────────────
[F6.2] P10/P50/P90 BANDBREEDTE
──────────────────────────────────────────────────────────────
Extend ForecastResult (models.py, frozen=True) met: p10, p50, p90.
Bereken std_dev per weekdag uit laatste 8 datapunten in sales_history.
  P10 = mean − 1.28 × std_dev
  P90 = mean + 1.28 × std_dev
  Fallback op ±15% bij <4 datapunten.
Toon als bereik-balk in views/page_forecast.py naast centrale voorspelling.
Test nieuwe ForecastResult-velden in tests/test_models.py.

──────────────────────────────────────────────────────────────
[F6.3] MAPE DASHBOARD UITBOUWEN
──────────────────────────────────────────────────────────────
views/page_leerrapport.py bestaat al als stub — UITBOUWEN, niet herbouwen.
Databron: forecast_log (predicted_covers, actual_covers).
NIET herbouwen: importeer learning.laad_accuracy_overzicht() voor MAPE.
Voeg toe:
  - MAPE per weekdag
  - Rollend 8-weken venster
  - Kleurcodering: groen <10% · geel 10–20% · rood >20%
