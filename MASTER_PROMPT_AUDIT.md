# AUDIT ACTIEPLAN — MASTER PROMPT
# Restaurant Besteltool · Productie-gereedheid
# Versie: AFGEROND · Aangemaakt: 2026-04-23 · Bijgewerkt: 2026-04-24

================================================================
STATUS: AUDIT VOLLEDIG AFGEROND
================================================================
Alle 6 auditfases zijn compleet. De besteltool is productie-gereed.

De codewijzigingen van fase A6 staan in de werkdirectory klaar om
te committen. Er zijn twee handmatige acties nodig voordat A6 ook
operationeel is:

  1. Voer supabase_migration_v13_audit_log.sql uit in Supabase
     (Dashboard → SQL Editor → plakken → Run)
  2. Commit + push naar main zodat de weekly_audit_email workflow
     in GitHub Actions actief wordt (cron maandag 08:00 UTC)

================================================================
AUDIT AFGEROND — OVERZICHT
================================================================

A1 Kritieke fixes                     ✅ DONE (2026-04-23)
A2 Staging + CI/CD                    ✅ DONE (2026-04-23)
A3 Password reset + tenant onboarding ✅ DONE (2026-04-23)
A4 RLS + JWT enforcement              ✅ DONE (2026-04-24)
A5 Centraal dashboard + notificaties  ✅ DONE (2026-04-24)
A6 Audit logs + wekelijkse rapportage ✅ DONE (2026-04-24)

================================================================
A6 — WAT ER OPGELEVERD IS
================================================================

Nieuwe bestanden:
  supabase_migration_v13_audit_log.sql    — audit_log tabel + RLS policy
  audit.py                                 — log_audit_event() helper
  scripts/stuur_audit_email.py             — wekelijkse samenvatting
  .github/workflows/weekly_audit_email.yml — cron maandag 08:00 UTC

Aangepaste bestanden:
  db.py                 — audit-logging bij maak_gebruiker_aan + maak_tenant_met_admin
  app.py                — login event wordt gelogd
  views/page_closing.py — sluiting_opgeslagen event wordt gelogd
  views/page_export.py  — bestelling_verzonden event wordt gelogd

Gelogde acties:
  - login
  - sluiting_opgeslagen  {datum, covers, omzet}
  - bestelling_verzonden {leverancier, datum, aantal}
  - gebruiker_aangemaakt {username, role}
  - tenant_aangemaakt    {naam, slug}

Wekelijkse e-mail inhoud (maandag 08:00 UTC per tenant):
  - Aantal acties per soort over afgelopen 7 dagen
  - Aantal unieke ingelogde gebruikers
  - Laatste 10 events met tijd, gebruiker en actie

================================================================
VOLGENDE FASES
================================================================
Feature-bouw (MASTER_PROMPT.md):
  Fase 3 van de feature-bouw wacht nog op uitvoering.
  Kopieer MASTER_PROMPT.md + zeg "Start FASE 3" in een nieuw gesprek.

================================================================
EINDE MASTER PROMPT AUDIT
================================================================
