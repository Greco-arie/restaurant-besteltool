# AUDIT ACTIEPLAN — MASTER PROMPT
# Restaurant Besteltool · Productie-gereedheid
# Versie: A5.0 · Aangemaakt: 2026-04-23 · Bijgewerkt: 2026-04-24

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
  email_service.py   → verzend_bestelling(), _genereer_pdf()
  monitoring.py      → log_event(), log_error(), stel_sentry_context_in()
  forecast.py        → bereken_forecast() en sub-functies
  recommendation.py  → bereken_alle_adviezen(), groepeer_per_leverancier()
  inventory.py       → laad_huidige_voorraad(), sla_sluitstock_op()
  learning.py        → bereken_correctiefactor(), laad_accuracy_overzicht()
  db.py              → get_client(), get_tenant_client(), laad_leveranciers_dict()
  models.py          → WeatherData, ForecastResult, UserSession, Product

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
  🟡 Geen centraal dashboard
  🟡 Geen proactieve notificaties
  🟡 Geen centrale audit log

================================================================
FASENOVERZICHT (volledig plan)
================================================================
A1  Kritieke fixes                     ✅ DONE (2026-04-23)
A2  Staging + CI/CD                    ✅ DONE (2026-04-23)
A3  Password reset + tenant onboarding ✅ DONE (2026-04-23)
A4  RLS + JWT enforcement              ✅ DONE (2026-04-24)
A5  Centraal dashboard + notificaties  ← ACTIEVE FASE
A6  Audit logs + wekelijkse rapportage

================================================================
██████████████████████████████████████████████████████████████
ACTIEVE FASE: A5 — CENTRAAL DASHBOARD + NOTIFICATIES
██████████████████████████████████████████████████████████████
================================================================

Doel: Manager ziet totaalplaatje op één pagina zonder in te loggen.
      Krijgt proactieve alerts zonder de app te hoeven openen.

----------------------------------------------------------------
STAP A5.1 — MANAGER DASHBOARD PAGINA
----------------------------------------------------------------
Maak views/page_dashboard.py aan met:
  - Omzet vandaag vs. gemiddeld (uit sales_history)
  - Covers vandaag vs. forecast (uit reservations of forecast_log)
  - Lage voorraad alert: producten onder minimumvoorraad
    (gebruik laad_huidige_voorraad() uit inventory.py)
  - Laatste 5 verzonden bestellingen (laad_verzonden_emails())
Toegang: alleen role manager, admin, super_admin (via permissions.py)
Gebruik get_tenant_client() voor alle queries.

----------------------------------------------------------------
STAP A5.2 — DAGELIJKSE FORECAST E-MAIL (22:00)
----------------------------------------------------------------
Maak .github/workflows/daily_forecast_email.yml aan:
  - Schedule: cron 0 22 * * * (22:00 UTC)
  - Roept een nieuw script aan: scripts/stuur_forecast_email.py
  - Script: laadt forecast voor morgen, stuurt via Resend
  - Gebruik service_key (GitHub secret) voor database-toegang
  Hergebruik: email_service.py patronen voor e-mail opmaak

----------------------------------------------------------------
STAP A5.3 — LAGE VOORRAAD ALERT BIJ CLOSING
----------------------------------------------------------------
Voeg toe aan views/page_closing.py (na opslaan sluitstock):
  - Controleer welke producten onder minimumvoorraad zitten
  - Als er producten zijn: stuur alert-e-mail naar manager
  - Gebruik bestaande email_service.py structuur
  - Alleen sturen als manager-email bekend is (tenant_users)

----------------------------------------------------------------
STOP CONDITIE FASE A5
----------------------------------------------------------------
Fase A5 is klaar wanneer ALLE punten groen zijn:

  [ ] page_dashboard.py aangemaakt en bereikbaar via navigatie
  [ ] Dashboard toont omzet, covers, lage voorraad, verzonden emails
  [ ] GitHub Actions workflow aangemaakt voor dagelijkse forecast e-mail
  [ ] Lage-voorraad alert getest bij closing (e-mail of log-bewijs)
  [ ] Commit + push naar main

----------------------------------------------------------------
FASE-AFSLUITING PROTOCOL (ALTIJD UITVOEREN NA STOP CONDITIE)
----------------------------------------------------------------
Wanneer alle stop-conditie punten groen zijn, voer dan VERPLICHT
de volgende drie acties uit in deze volgorde:

1. HERSCHRIJF DIT BESTAND (MASTER_PROMPT_AUDIT.md):
   - Markeer A5 als ✅ DONE
   - Vervang de ACTIEVE FASE sectie door FASE A6 inhoud

2. UPDATE PRIMER (C:\Users\MSI\.claude\primer.md):
   - A5 Dashboard + notif.: ✅ DONE ([datum])
   - A6 Audit logs: 🔄 ACTIEF

3. UPDATE MEMORY:
   C:\Users\MSI\.claude\projects\c--Users-MSI-Documents-AI-PROJECTEN\memory\audit_voortgang.md

4. ZEG TEGEN ARIS:
   "✅ Fase A5 afgerond. MASTER_PROMPT_AUDIT.md is bijgewerkt naar A6.
    Kopieer het bestand in een nieuwe chat om verder te gaan."

================================================================
FASE A6 (GLOBAAL)
================================================================
Doel: Elke actie is traceerbaar. Wekelijkse audit per restaurant.
Onderdelen:
  - audit_log tabel (wie, wat, wanneer, tenant)
  - Login events loggen
  - Wekelijkse audit e-mail per tenant (GitHub Actions)
  - Alert bij failures met root cause

================================================================
EINDE MASTER PROMPT AUDIT
================================================================
