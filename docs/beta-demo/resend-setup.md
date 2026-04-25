# Resend setup per tenant — DNS, verificatie & secrets

> Doel: een tenant kan e-mails versturen vanaf
> `no-reply@<tenant-slug>.besteltool.nl` zonder dat je code hoeft te
> wijzigen. De afzender-keuze gebeurt door
> `email_service._kies_afzender()` op basis van de
> `RESEND_VERIFIED_DOMAINS` lijst.

Voorbeeld in deze handleiding: tenant `family-maarssen` →
`family-maarssen.besteltool.nl`.

---

## 1. DNS-records bij de domeinregistrar

Je hebt voor elk subdomein vijf records nodig: SPF (op het subdomein én
op `send.<sub>`), MX (return-path voor bounces), DKIM (CNAME) en DMARC.
Resend toont deze in het scherm "Add Domain" zodra je het subdomein hebt
toegevoegd. Hieronder de generieke variant — neem altijd de exacte
waarden uit het Resend-scherm (de DKIM-CNAME-targets zijn per account
uniek).

| Type  | Naam                                       | Waarde                                                                 | TTL  |
|-------|--------------------------------------------|------------------------------------------------------------------------|------|
| TXT   | `family-maarssen.besteltool.nl`            | `v=spf1 include:amazonses.com ~all`                                    | 3600 |
| MX    | `send.family-maarssen.besteltool.nl`       | `feedback-smtp.eu-west-1.amazonses.com` (priority 10)                  | 3600 |
| TXT   | `send.family-maarssen.besteltool.nl`       | `v=spf1 include:amazonses.com ~all`                                    | 3600 |
| CNAME | `resend._domainkey.family-maarssen.besteltool.nl` | `<unieke-waarde-uit-resend>.dkim.amazonses.com`                  | 3600 |
| TXT   | `_dmarc.family-maarssen.besteltool.nl`     | `v=DMARC1; p=none;`                                                     | 3600 |

> **Belangrijk:** een CNAME mag niet samen met andere records op exact
> dezelfde naam staan. Daarom gebruikt Resend `resend._domainkey.<sub>`
> en `send.<sub>` als aparte hostnamen.

### Waarom vier records?

- **SPF** vertelt ontvangers dat AWS SES (de provider achter Resend) mag
  verzenden namens jouw domein.
- **DKIM** zet een cryptografische handtekening op elke mail.
- **DMARC** vertelt ontvangers wat te doen als SPF/DKIM falen.
- **MX op `send.`** vangt bounce-meldingen op zodat Resend weet welke
  adressen niet bezorgd zijn.

---

## 2. Domein toevoegen in Resend

1. Login op <https://resend.com/domains>.
2. Klik **"Add Domain"** → vul `family-maarssen.besteltool.nl` in.
3. Kopieer de getoonde records één-voor-één naar je registrar (zie tabel
   hierboven; pak de exacte waarden uit het Resend-scherm).
4. Klik **"Verify DNS Records"**. Status `Pending` → na propagatie
   (meestal <15 min, soms tot 24u) wordt dit `Verified`.
5. Verschijnt na ±30 min nog steeds `Pending`? Controleer met
   `dig TXT family-maarssen.besteltool.nl +short` of de records
   leesbaar zijn vanaf publieke DNS.

---

## 3. Secrets zetten

### GitHub (CI / repo-secrets)

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`:

```
Name:  RESEND_VERIFIED_DOMAINS
Value: family-maarssen.besteltool.nl
```

Bij meerdere tenants: comma-separated, geen spaties nodig (whitespace
wordt geslikt door de helper).

```
Value: family-maarssen.besteltool.nl,demo.besteltool.nl
```

### Streamlit Cloud (productie)

`App` → `Settings` → `Secrets` → voeg toe in TOML-formaat:

```toml
RESEND_VERIFIED_DOMAINS = "family-maarssen.besteltool.nl"
```

Streamlit herstart de app automatisch zodra je opslaat.

### Lokaal (`.env`)

```
RESEND_VERIFIED_DOMAINS=family-maarssen.besteltool.nl
```

---

## 4. Verifiëren in productie

Zodra DNS verified is en de secret staat:

1. Open de app als manager van de betreffende tenant.
2. Trigger één testmail (bijvoorbeeld een wachtwoord-reset of een
   testbestelling naar je eigen adres).
3. Check de mail-headers: `From:` moet
   `no-reply@family-maarssen.besteltool.nl` zijn — niet
   `onboarding@resend.dev`.
4. Check Streamlit logs op `resend_sandbox_afzender` — die mag NIET
   verschijnen voor een verified tenant.

---

## 5. Backwards-compat: legacy flag

`RESEND_DOMEIN_GEVERIFIEERD=true` blijft werken als blanket allow voor
**alle** tenants. Dit is bedoeld voor de overgangsperiode terwijl je nog
maar één tenant hebt verified. Bij gebruik logt de helper een
`resend_legacy_flag_deprecated` warning. Verwijder de flag zodra je
nieuwe lijst alle relevante tenants dekt.

---

## 6. Troubleshooting

| Symptoom                               | Oorzaak                                            | Oplossing |
|----------------------------------------|----------------------------------------------------|-----------|
| Mail komt nooit aan, geen Resend-event | API key fout of onbestaand                          | Controleer `RESEND_API_KEY` in secrets |
| Mail komt aan vanaf `onboarding@resend.dev` | tenant niet in `RESEND_VERIFIED_DOMAINS`     | Voeg `<slug>.besteltool.nl` toe (case-insensitive, whitespace ok) |
| Resend toont status `Failed`           | DKIM- of SPF-record ontbreekt of staat fout         | Vergelijk met de waarden in het "Add Domain"-scherm |
| Mail belandt in spam                   | DMARC nog niet gepropageerd of Reply-To ontbreekt   | Wacht 24u; voeg eventueel `v=DMARC1; p=none; rua=mailto:postmaster@...` toe |
| Bounce-meldingen worden niet zichtbaar | `MX send.<sub>` ontbreekt                           | Voeg de MX-record toe en wacht op propagatie |
