# AUDIT ACTIEPLAN — MASTER PROMPT
# Restaurant Besteltool · Productie-gereedheid
# Versie: A6.0 · Aangemaakt: 2026-04-23 · Bijgewerkt: 2026-04-24

================================================================
HOE TE GEBRUIKEN
================================================================
1. Kopieer dit volledige document in een nieuw gesprek
2. Claude leest ACTIEVE FASE en weet precies wat te doen
3. Claude stopt zodra de stop-conditie bereikt is
4. Claude genereert dan automatisch een nieuwe versie van dit bestand
   (ACTIEVE FASE gaat naar de volgende) + update memory
5. Jij kopieert het nieuwe bestand voor de volgende sessie

Elke fase is bewust klein — zodat Claude onder 50% context-gebruik blijft.
Zeg "ga verder" als je wil beginnen. Zeg "sla op en stop" als je wil pauzeren.

================================================================
ROL
================================================================
Senior full-stack engineer + security reviewer.
Productiegericht: lever pas op als iets aantoonbaar werkt.
Spreek Nederlands naar de manager, Engels in code en commits.

NIET HERBOUWEN wat al bestaat:
  email_service.py   → verzend_bestelling(), _genereer_pdf(), verzend_lage_voorraad_alert()
  monitoring.py      → log_event(), log_error(), stel_sentry_context_in()
  forecast.py        → bereken_forecast() en sub-functies
  recommendation.py  → bereken_alle_adviezen(), groepeer_per_leverancier()
  inventory.py       → laad_huidige_voorraad(), sla_sluitstock_op()
  learning.py        → bereken_correctiefactor(), laad_accuracy_overzicht()
  db.py              → get_client(), get_tenant_client(), laad_leveranciers_dict()
  models.py          → WeatherData, ForecastResult, UserSession, Product
  views/page_dashboard.py → render() (dashboard A5)

================================================================
PROJECTCONTEXT (niet opnieuw uitleggen — vertrouw hierop)
================================================================
Stack:      Python 3.13 · Streamlit Cloud (live) · Supabase PostgreSQL
Auth:       bcrypt via RPC verificeer_login(p_tenant_slug, p_username, p_password)
Rollen:     user < manager < admin < super_admin
Klant #1:   Family Maarssen (tenant slug: family-maarssen, id: 11111111-1111-1111-1111-111111111111)
Superadmin: platform-tenant (v8 migratie)
Email:      Resend API (geconfigureerd, sandbox modus)
Monitoring: Sentry + structlog → stdout
GitNexus:   geindexeerd (1236 nodes, 31 flows) — gebruik gitnexus_impact voor elke edit

RLS architectuur (A4, 2026-04-24):
  get_tenant_client(tenant_id) → JWT signed met anon_key + jwt_secret
  JWT claims: { role: "authenticated", tenant_id: "...", sub: "..." }
  RLS policies op 9 tabellen via tenant_jwt_id() hulpfunctie
  service_role bypast RLS — alleen voor admin-functies

Bekende technische schuld (volledig gedocumenteerd in audit van 2026-04-23):
  ✅ email_service.py:172 → hardcoded to_email OPGELOST (2026-04-23)
  ✅ email_service.py:177 → hardcoded afzender OPGELOST (2026-04-23)
  ✅ .streamlit/secrets.toml → nooit ge-commit, staat in .gitignore BEVESTIGD
  ✅ Geen session timeout OPGELOST (2026-04-23)
  ✅ Geen staging omgeving OPGELOST (2026-04-23)
  ✅ Geen CI/CD pipeline OPGELOST (2026-04-23)
  ✅ Geen password reset flow OPGELOST (2026-04-23)
  ✅ Geen self-service tenant onboarding OPGELOST (2026-04-23)
  ✅ RLS omzeild via service_role OPGELOST (2026-04-24)
  ✅ Geen centraal dashboard OPGELOST (2026-04-24)
  ✅ Geen proactieve notificaties OPGELOST (2026-04-24)
  🟡 Geen centrale audit log

================================================================
FASENOVERZICHT (volledig plan)
================================================================
A1  Kritieke fixes                     ✅ DONE (2026-04-23)
A2  Staging + CI/CD                    ✅ DONE (2026-04-23)
A3  Password reset + tenant onboarding ✅ DONE (2026-04-23)
A4  RLS + JWT enforcement              ✅ DONE (2026-04-24)
A5  Centraal dashboard + notificaties  ✅ DONE (2026-04-24)
A6  Audit logs + wekelijkse rapportage ← ACTIEVE FASE

================================================================
██████████████████████████████████████████████████████████████
ACTIEVE FASE: A6 — AUDIT LOGS + WEKELIJKSE RAPPORTAGE
██████████████████████████████████████████████████████████████
================================================================

Doel: Elke actie is traceerbaar. Wekelijkse audit per restaurant.

----------------------------------------------------------------
STAP A6.1 — AUDIT LOG TABEL (SUPABASE MIGRATIE)
----------------------------------------------------------------
Maak supabase_migration_v13_audit_log.sql aan:
  CREATE TABLE audit_log (
    id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id    uuid NOT NULL REFERENCES tenants(id),
    user_naam    text NOT NULL,
    actie        text NOT NULL,   -- bijv. 'login', 'bestelling_verzonden', 'voorraad_opgeslagen'
    details      jsonb,           -- extra context (leverancier, bedrag, etc.)
    created_at   timestamptz DEFAULT now()
  );
  RLS: tenant_id = auth.jwt() ->> 'tenant_id' (lezen)
       INSERT via service_role (schrijven vanuit app)
  Index op tenant_id + created_at

----------------------------------------------------------------
STAP A6.2 — LOGIN EVENTS LOGGEN
----------------------------------------------------------------
Voeg toe aan app.py (na succesvolle login in page_login()):
  - log_audit_event(tenant_id, user_naam, 'login', {})
Maak db.py functie: log_audit_event(tenant_id, user_naam, actie, details)
  - Schrijft via service_role (bypast RLS)
  - Gooit nooit een exception naar de caller (try/except intern)

----------------------------------------------------------------
STAP A6.3 — KERNACTIES LOGGEN
----------------------------------------------------------------
Log de volgende acties in de bestaande code:
  - views/page_closing.py  → 'sluiting_opgeslagen'  {covers, omzet}
  - views/page_review.py   → 'bestelling_verzonden'  {leverancier, datum}
  - db.py maak_gebruiker_aan() → 'gebruiker_aangemaakt' {username, role}
  - db.py maak_tenant_aan()   → 'tenant_aangemaakt'    {naam, slug}

----------------------------------------------------------------
STAP A6.4 — WEKELIJKSE AUDIT E-MAIL (GITHUB ACTIONS)
----------------------------------------------------------------
Maak .github/workflows/weekly_audit_email.yml aan:
  - Schedule: cron 0 8 * * 1 (maandag 08:00 UTC)
  - Script: scripts/stuur_audit_email.py
  - Per tenant: samenvatting van de afgelopen 7 dagen
    (logins, bestellingen, sluitingen, gebruikerswijzigingen)
  - Stuur naar manager/admin e-mailadressen van die tenant

----------------------------------------------------------------
STOP CONDITIE FASE A6
----------------------------------------------------------------
Fase A6 is klaar wanneer ALLE punten groen zijn:

  [ ] supabase_migration_v13_audit_log.sql aangemaakt
  [ ] Migratie uitgevoerd in Supabase (bewijs: tabel bestaat)
  [ ] log_audit_event() in db.py aangemaakt
  [ ] Login events worden gelogd
  [ ] Minimaal 3 kernacties worden gelogd (sluiting, bestelling, gebruiker)
  [ ] GitHub Actions workflow aangemaakt voor wekelijkse audit e-mail
  [ ] Commit + push naar main

----------------------------------------------------------------
FASE-AFSLUITING PROTOCOL (ALTIJD UITVOEREN NA STOP CONDITIE)
----------------------------------------------------------------
Wanneer alle stop-conditie punten groen zijn, voer dan VERPLICHT
de volgende acties uit:

1. HERSCHRIJF DIT BESTAND (MASTER_PROMPT_AUDIT.md):
   - Markeer A6 als ✅ DONE
   - Voeg sectie "AUDIT AFGEROND" toe — alle 6 fases compleet

2. UPDATE PRIMER (C:\Users\MSI\.claude\primer.md):
   - A6 Audit logs: ✅ DONE ([datum])
   - Audit actieplan: VOLLEDIG AFGEROND

3. UPDATE MEMORY:
   C:\Users\MSI\.claude\projects\c--Users-MSI-Documents-AI-PROJECTEN\memory\audit_voortgang.md

4. ZEG TEGEN ARIS:
   "✅ Fase A6 afgerond. Alle 6 auditfases zijn nu compleet.
    De besteltool is productie-gereed."

================================================================
EINDE MASTER PROMPT AUDIT
================================================================
