# Admin: wachtwoord-reset-link sturen

> Korte handleiding voor super_admin (jij) en restaurant-admins/managers
> die collega's willen helpen die hun wachtwoord kwijt zijn.

## Wat is dit

In plaats van plaintext wachtwoorden te bewaren of te tonen
(privacy-overtreding én technisch onmogelijk omdat we bcrypt-hashes
opslaan), stuurt deze knop een **eenmalige reset-link** naar het
e-mailadres van de medewerker. De medewerker kiest dan zelf een nieuw
wachtwoord — exact dezelfde flow als de zelfservice "Wachtwoord
vergeten?" link op het loginscherm.

## Wie kan de knop zien

| Pagina        | Rol         | Scope                              |
| ------------- | ----------- | ---------------------------------- |
| Beheer        | super_admin | Cross-tenant, alle gebruikers      |
| Instellingen  | admin       | Eigen tenant                       |
| Instellingen  | manager     | Eigen tenant — mits recht          |
|               |             | "gebruikers_beheren" aangevinkt    |

Gebruikers zonder dit recht zien de knop niet (UI-laag) en de helper
weigert ook server-side (defense-in-depth).

## Stap voor stap (vanuit de UI)

1. Open **Beheer** (super_admin) of **Instellingen → Gebruikers**
   (admin/manager).
2. Klap de medewerker open via de expander.
3. **Vul indien nodig eerst een e-mailadres in** en klik *Opslaan*.
   Zonder e-mail is de knop uitgegrijsd.
4. Klik **"Stuur reset-link"** onderaan de gebruiker-card.
5. Bevestig in het pop-up-paneel: *"Stuur een reset-link naar
   xxx@yyy.nl?"* → klik **"Ja, verstuur"**.
6. Je ziet een groene melding: *"Reset-link verstuurd naar
   xxx@yyy.nl."*

De medewerker ontvangt een mail met een knop, klikt erop, kiest een
nieuw wachtwoord, en kan direct weer inloggen.

## Wat gebeurt er onder de motorkap

```
admin klikt "Stuur reset-link"
  └─ permission-check (gebruikers_beheren)
  └─ e-mail-check (anders disabled)
  └─ basis-URL-check (secrets/env)
  └─ db.maak_reset_token(tenant_id, user_id)         ← eenmalig token
  └─ email_service.verzend_reset_mail(...)            ← Resend API
  └─ audit.log_audit_event(target_tenant, ...)        ← forensics
```

**Audit-trail.** Elke klik wordt vastgelegd in `audit_log` in de tenant
van de **target** (niet de actor). Reden: forensisch onderzoek hoort
plaats te vinden waar de getroffen data leeft. Velden:

| Veld              | Inhoud                                       |
| ----------------- | -------------------------------------------- |
| `actor_rol`       | super_admin / admin / manager                |
| `target_user_id`  | UUID van de medewerker                       |
| `target_username` | gebruikersnaam (handig voor zoeken)          |
| `target_tenant_id`| tenant van de medewerker                     |
| `cross_tenant`    | True als super_admin een andere tenant raakt |
| `mail_sent`       | True/False (of Resend de mail accepteerde)   |

## Foutmeldingen

| Melding                                | Wat te doen                          |
| -------------------------------------- | ------------------------------------ |
| Knop is uitgegrijsd                    | Vul eerst een e-mailadres in.        |
| "App-basis-URL ontbreekt"              | Configureer `app.base_url` in        |
|                                        | `.streamlit/secrets.toml` of de      |
|                                        | `APP_BASE_URL` env var.              |
| "Token aanmaken mislukt"               | Probeer opnieuw; als het blijft      |
|                                        | mislukken: check Supabase            |
|                                        | connectiviteit.                      |
| "Versturen mislukt: smtp_error" (etc.) | Resend-fout. Check Resend-dashboard  |
|                                        | of het verified-domains-veld.        |

## Waarom geen plaintext-wachtwoorden tonen

1. **Technisch onmogelijk.** Wachtwoorden worden opgeslagen als
   bcrypt-hashes (one-way). Plaintext kan niet worden teruggehaald uit
   de database — alleen vervangen.
2. **Privacy/AVG.** Het tonen of opslaan van plaintext-wachtwoorden
   schendt de minimum-noodzaak-eis: support hoort het wachtwoord van
   een gebruiker nooit te kennen.
3. **Industry standard.** Auth0, Google Workspace, Microsoft 365 — geen
   enkele serieuze auth-provider toont plaintext. Een
   reset-flow is de juiste primitief.
