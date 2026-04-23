# FASE 3 — SECURITY-HARDENING
# Vereiste: Fase 1 klaar.
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
[F3.1] RLS — ECHTE DATABASE-ISOLATIE
──────────────────────────────────────────────────────────────
PROBLEEM: service_role bypassed RLS altijd (Supabase API-niveau). FORCE RLS helpt niet.
OPLOSSING: tenant-operaties via anon_key + JWT met tenant_id claim.

Benodigde secrets (Aris voegt toe in Streamlit Cloud + .streamlit/secrets.toml):
  [supabase]
  anon_key  = "..."   # Supabase → Settings → API → anon public
  jwt_secret = "..."  # Supabase → Settings → API → JWT Secret

SQL (supabase_migration_v8_rls.sql):
  -- Enable RLS op alle tenant-tabellen
  ALTER TABLE tenant_users ENABLE ROW LEVEL SECURITY;
  ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
  ALTER TABLE sales_history ENABLE ROW LEVEL SECURITY;
  ALTER TABLE stock_count ENABLE ROW LEVEL SECURITY;
  ALTER TABLE forecast_log ENABLE ROW LEVEL SECURITY;
  ALTER TABLE current_inventory ENABLE ROW LEVEL SECURITY;
  ALTER TABLE inventory_adjustments ENABLE ROW LEVEL SECURITY;
  ALTER TABLE daily_usage ENABLE ROW LEVEL SECURITY;
  ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

  -- Policies: tenant-tabellen (tenant_id claim in JWT)
  CREATE POLICY tenant_access ON tenant_users FOR ALL
    USING (tenant_id::text = auth.jwt() ->> 'tenant_id');
  -- herhaal voor alle 8 tenant-tabellen

  -- tenants-tabel: alleen super_admin
  CREATE POLICY admin_only ON tenants FOR ALL
    USING ((auth.jwt() ->> 'app_role') = 'super_admin');

db.py wijzigingen:
  import jwt  # PyJWT
  from datetime import datetime, timedelta, timezone

  def _maak_tenant_jwt(tenant_id: str, app_role: str = 'authenticated') -> str:
      now = datetime.now(timezone.utc)
      payload = {
          'iss': 'supabase', 'role': 'authenticated',
          'iat': int(now.timestamp()),
          'exp': int((now + timedelta(hours=1)).timestamp()),
          'tenant_id': tenant_id, 'app_role': app_role,
      }
      return jwt.encode(payload, st.secrets["supabase"]["jwt_secret"], algorithm='HS256')

  def get_tenant_client(tenant_id: str) -> Client:
      """Anon client met tenant-JWT — RLS actief."""
      url  = st.secrets["supabase"]["url"]
      anon = st.secrets["supabase"]["anon_key"]
      token = _maak_tenant_jwt(tenant_id)
      return create_client(url, anon, options=ClientOptions(
          headers={"apikey": anon, "Authorization": f"Bearer {token}"}
      ))

  def get_admin_client() -> Client:
      """Service role — alleen voor super_admin cross-tenant operaties."""
      url = st.secrets["supabase"]["url"]
      key = st.secrets["supabase"]["service_key"]
      return create_client(url, key)

  Hernoem get_client() → get_admin_client() overal waar cross-tenant nodig is.
  Vervang get_client() → get_tenant_client(tenant_id) in alle tenant-functies.

Tests (tests/test_rls.py):
  Voor elke tabel: query met tenant_id A via JWT van tenant B → MOET leeg retourneren.
  Gebruik pytest + anon_key rechtstreeks.

Documenteer elke policy in docs/rls-policies.md.

──────────────────────────────────────────────────────────────
[F3.2] 2FA VIA TOTP
──────────────────────────────────────────────────────────────
App gebruikt EIGEN bcrypt-login. NIET via Supabase Auth MFA.
Implementeer met pyotp + qrcode.

SQL (supabase_migration_v10_2fa.sql):
  ALTER TABLE tenant_users
    ADD COLUMN mfa_secret TEXT,
    ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;

Bouw views/setup_2fa_page.py:
(a) Genereer secret: pyotp.random_base32()
(b) Toon QR-code: qrcode → base64 PNG → st.image()
(c) Verifieer code: pyotp.TOTP(secret).verify(code)
(d) Sla op in tenant_users: mfa_secret + mfa_enabled=TRUE via db.py

Pas app.py login-flow aan:
  - Na succesvolle wachtwoord-check: als mfa_enabled → TOTP-verificatiestap
  - Managers (>= manager) die mfa_enabled=FALSE zijn → geforceerde setup bij eerste login
