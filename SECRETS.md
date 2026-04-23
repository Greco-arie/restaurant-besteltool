# Secrets — wat aanmaken en waar instellen

Dit bestand legt uit welke API-keys je nodig hebt, waar je ze aanmaakt,
en hoe je ze instelt op Streamlit Cloud en als GitHub Actions secrets.

---

## 1. Resend — transactionele e-mail (Feature 1.1)

**Waarvoor:** bestellingen als PDF mailen naar leveranciers + BCC aan de manager.

**Aanmaken:**
1. Ga naar https://resend.com en maak een gratis account aan
2. Verifieer een domein (of gebruik `onboarding@resend.dev` voor testen)
3. Ga naar API Keys → Create API Key → geef volledige Send-rechten
4. Kopieer de key (begint met `re_`)

**Instellen op Streamlit Cloud:**
- App Settings → Secrets → voeg toe:
  ```toml
  [resend]
  api_key = "re_xxxxxxxxxxxxxxxxxxxx"
  ```

**Instellen als GitHub Actions secret (optioneel):**
- Repo → Settings → Secrets and variables → Actions → New secret
- Naam: `RESEND_API_KEY`, waarde: `re_xxxxxxxxxxxxxxxxxxxx`

---

## 2. Sentry DSN — error tracking (Feature 1.2)

**Waarvoor:** automatisch fouten in het Sentry dashboard zien, met tenant/user/pagina tags.

**Aanmaken:**
1. Ga naar https://sentry.io en maak een gratis account aan
2. Maak een nieuw project: Python → Streamlit (kies gewoon "Python")
3. Kopieer de DSN (begint met `https://`)

**Instellen op Streamlit Cloud:**
- App Settings → Secrets → voeg toe:
  ```toml
  [sentry]
  dsn = "https://xxxxxxxxxxxxxxx@oxxxxxx.ingest.sentry.io/xxxxxxx"
  ```

**Test of het werkt:**
- Roep `monitoring.veroorzaak_test_exception()` aan via een tijdelijke knop in de app
- Controleer Sentry dashboard: je moet een exception zien met tenant_id en pagina tags

---

## 3. Backblaze B2 + GPG — dagelijkse backup (Feature 1.3)

**Waarvoor:** versleutelde pg_dump elke nacht bewaren, retentie 30 dagen.

### 3a. Backblaze B2 bucket aanmaken
1. Ga naar https://www.backblaze.com/b2/cloud-storage.html
2. Maak een account aan (eerste 10 GB gratis)
3. Buckets → Create a Bucket:
   - Naam: `besteltool-backups`
   - Files in Bucket: Private
   - Default Encryption: Enabled
4. Note de endpoint-URL (bijv. `https://s3.eu-central-003.backblazeb2.com`)

### 3b. B2 Application Key aanmaken
1. App Keys → Add a New Application Key
2. Geef toegang tot bucket `besteltool-backups`, alleen `Read and Write`
3. Kopieer keyID en applicationKey

### 3c. Supabase database-credentials ophalen
1. Supabase dashboard → Project Settings → Database
2. Kopieer: Host, User (postgres), Password, Database name

### 3d. GPG passphrase kiezen
- Kies een sterk wachtwoord (minimaal 32 tekens)
- Bewaar dit in een wachtwoordmanager — zonder dit kun je de backup NIET ontsleutelen

### 3e. GitHub Actions secrets instellen
Ga naar: Repo → Settings → Secrets and variables → Actions → New secret

| Secret naam              | Waarde                                              |
|--------------------------|-----------------------------------------------------|
| `SUPABASE_DB_HOST`       | db.xxxxxxxxxxxxxxxxxxxx.supabase.co                 |
| `SUPABASE_DB_USER`       | postgres                                            |
| `SUPABASE_DB_PASSWORD`   | [jouw database wachtwoord]                          |
| `SUPABASE_DB_NAME`       | postgres                                            |
| `B2_KEY_ID`              | [Backblaze keyID]                                   |
| `B2_APPLICATION_KEY`     | [Backblaze applicationKey]                          |
| `B2_BUCKET_NAME`         | besteltool-backups                                  |
| `B2_ENDPOINT`            | https://s3.eu-central-003.backblazeb2.com           |
| `BACKUP_GPG_PASSPHRASE`  | [jouw GPG wachtwoord — bewaar dit goed!]            |

### 3f. Backup handmatig testen
1. Ga naar GitHub repo → Actions → "Dagelijkse Supabase backup"
2. Klik "Run workflow" → wacht tot de run groen is
3. Ga naar Backblaze B2 dashboard → besteltool-backups → backups/
4. Download het .gpg bestand en ontsleutel lokaal:
   ```bash
   gpg --batch --passphrase "JOUW_WACHTWOORD" \
       --decrypt backup_2025-01-01.sql.gpg > backup_test.sql
   ```
5. Herstel op een lege testdatabase:
   ```bash
   pg_restore --host=... --username=postgres --dbname=testdb backup_test.sql
   ```

---

## Streamlit Cloud secrets — compleet voorbeeld

De veldnamen hieronder matchen exact wat de code leest (`db.py`, `email_service.py`,
`monitoring.py`). Wijzig ze niet — anders werken de integraties niet.

```toml
[supabase]
url         = "https://xxxxxxxxxxxxxxxxxxxx.supabase.co"
service_key = "sb_secret_xxxxxxxxxxxxxxxxxxxx"

[resend]
api_key = "re_xxxxxxxxxxxxxxxxxxxx"

[sentry]
dsn = "https://xxxxxxxxxxxxxxx@oxxxxxx.ingest.sentry.io/xxxxxxx"
```
