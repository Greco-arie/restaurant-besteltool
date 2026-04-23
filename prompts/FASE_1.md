# FASE 1 — PRODUCTIE-FUNDAMENT
# Vereiste: geen. Dit zijn de blockers voor de eerste klant.
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
[F1.1] SENT_EMAILS TABEL + RESEND-VERIFICATIE
──────────────────────────────────────────────────────────────
email_service.py is VOLLEDIG GEBOUWD. Raak verzend_bestelling() NIET aan.

(a) Nieuwe tabel (supabase_migration_v8_sent_emails.sql):
    CREATE TABLE sent_emails (
      id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id     UUID NOT NULL REFERENCES tenants(id),
      supplier_id   UUID REFERENCES suppliers(id),
      supplier_naam TEXT,
      bestel_datum  DATE,
      resend_id     TEXT,
      status        TEXT NOT NULL DEFAULT 'sent',
      timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    RLS policy op tenant_id.

(b) Pas views/page_export.py aan: na elke succesvolle verzend_bestelling()-call
    insert een rij in sent_emails via db.get_client().

(c) Controleer bij app-start of RESEND_API_KEY aanwezig is in secrets;
    log via monitoring.log_event() als de key ontbreekt.

──────────────────────────────────────────────────────────────
[F1.2] SENTRY VERIFICATIE
──────────────────────────────────────────────────────────────
monitoring.py is VOLLEDIG GEBOUWD. Raak dit bestand NIET aan.

(a) Verifieer SENTRY_DSN in productie-secrets. Zo niet: documenteer exact
    welke stap Aris moet uitvoeren (Sentry project → DSN → Streamlit Cloud secrets).

(b) Voeg verborgen "Sentry test"-knop toe in views/page_admin.py
    (alleen super_admin): roept monitoring.veroorzaak_test_exception() aan.

(c) Verifieer dat app.py stel_sentry_context_in() aanroept bij elke paginawissel;
    voeg toe als het ontbreekt.

──────────────────────────────────────────────────────────────
[F1.3] DAGELIJKSE BACKUP
──────────────────────────────────────────────────────────────
Kies én documenteer: GitHub Actions (eenvoudig, aanbevolen) of Celery (als Redis al loopt).

GitHub Actions (.github/workflows/backup.yml):
  schedule: cron('0 3 * * *')
  1. pg_dump → versleuteld .sql.gz (gpg --symmetric, passphrase = GPG_PASSPHRASE secret)
  2. Upload naar Backblaze B2 (B2_BUCKET_NAME, B2_KEY_ID, B2_APP_KEY)
  3. Verwijder bestanden ouder dan 30 dagen

Lever SECRETS_CHECKLIST.md (niet committen) met exacte secrets die Aris moet aanmaken.
Lever restore-instructies als commentaar in backup.yml.
