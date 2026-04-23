# FASE 9 — ACHTERGRONDTAKEN + CLOUD AUTOMATION
# Vereiste: Fase 7 (FastAPI). Kies GitHub Actions OF Celery — documenteer keuze.
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
KEUZE: GitHub Actions (aanbevolen als Redis niet loopt) vs. Celery (als Redis al actief is)
──────────────────────────────────────────────────────────────
Documenteer keuze + reden in workers/README.md of .github/workflows/README.md.

──────────────────────────────────────────────────────────────
[F9.1] DAGELIJKSE FORECAST HERBEREKENING (22:00)
──────────────────────────────────────────────────────────────
Herbereken forecast voor morgen voor alle actieve tenants.
Sla op in forecast_log (voorspelling zonder werkelijke covers).
NIET herbouwen: importeer bereken_forecast() uit forecast.py.

GitHub Actions: .github/workflows/daily_forecast.yml · cron('0 22 * * *')
Celery:         workers/tasks/daily_forecast.py · beat_schedule 22:00

──────────────────────────────────────────────────────────────
[F9.2] DAGELIJKSE ANALYTICS UPDATE (06:00)
──────────────────────────────────────────────────────────────
Herbereken analytics_service aggregaties voor gisteren.
Sla gecachede resultaten op (Redis of analytics_cache tabel in Supabase).

──────────────────────────────────────────────────────────────
[F9.3] DAGELIJKSE BACKUP (03:00 UTC)
──────────────────────────────────────────────────────────────
Als F1.3 gekozen heeft voor GitHub Actions: deze taak is al klaar, overslaan.
Als Celery: workers/tasks/daily_backup.py — zelfde logica als F1.3.

──────────────────────────────────────────────────────────────
[F9.4] DREMPELWAARDEN PER TENANT
──────────────────────────────────────────────────────────────
SQL (supabase_migration_v15_tenant_config.sql):
  ALTER TABLE tenants
    ADD COLUMN low_stock_alert_pct  NUMERIC DEFAULT 0.20,
    ADD COLUMN food_cost_alert_pct  NUMERIC DEFAULT 0.38;

Gebruik in achtergrondtaken voor alert-logica.
