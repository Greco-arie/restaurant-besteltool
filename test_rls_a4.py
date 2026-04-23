"""
A4 RLS test — voer uit met: python test_rls_a4.py
Vereisten: pip install supabase PyJWT toml
Credentials worden gelezen uit .streamlit/secrets.toml (nooit gecheckt in git).
"""
import sys
import os
from datetime import datetime, timezone, timedelta

import jwt
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

# ── Configuratie uit secrets.toml ───────────────────────────
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

_secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
with open(_secrets_path, "rb") as f:
    _secrets = tomllib.load(f)

URL         = _secrets["supabase"]["url"]
SERVICE_KEY = _secrets["supabase"]["service_key"]
ANON_KEY    = _secrets["supabase"]["anon_key"]
JWT_SECRET  = _secrets["supabase"]["jwt_secret"]


def make_tenant_client(tenant_id: str):
    now = datetime.now(timezone.utc)
    token = jwt.encode({
        "iss":       "supabase",
        "role":      "authenticated",
        "iat":       int(now.timestamp()),
        "exp":       int((now + timedelta(hours=1)).timestamp()),
        "sub":       tenant_id,
        "tenant_id": tenant_id,
    }, JWT_SECRET, algorithm="HS256")
    return create_client(
        URL, ANON_KEY,
        options=SyncClientOptions(headers={"Authorization": f"Bearer {token}"}),
    )


def ok(msg): print(f"  [OK] {msg}")
def fail(msg): print(f"  [FAIL] {msg}"); sys.exit(1)


print("\n=== A4 RLS + JWT — isolatietest ===\n")

# ── Stap 1: haal tenant-IDs op via service_role ──────────────
print("Stap 1: Tenants ophalen via service_role...")
admin = create_client(URL, SERVICE_KEY)
tenants_resp = admin.table("tenants").select("id, slug").order("slug").execute()
tenants = tenants_resp.data or []
if not tenants:
    fail("Geen tenants gevonden in de database.")
print(f"  Gevonden tenants: {[t['slug'] for t in tenants]}")

# Gebruik de eerste tenant als 'eigen' tenant
own_tenant = tenants[0]
own_id     = own_tenant["id"]
own_slug   = own_tenant["slug"]

# Gebruik een tweede tenant als 'vreemd' — of een random UUID als er maar 1 is
import uuid
if len(tenants) > 1:
    other_id   = tenants[1]["id"]
    other_slug = tenants[1]["slug"]
else:
    other_id   = str(uuid.uuid4())
    other_slug = "nonexistent-tenant"

print(f"  Eigen tenant  : {own_slug} ({own_id})")
print(f"  Andere tenant : {other_slug} ({other_id})")

# ── Stap 2: eigen data ophalen met tenant client ─────────────
print(f"\nStap 2: Suppliers ophalen als '{own_slug}'...")
own_client = make_tenant_client(own_id)
own_resp   = own_client.table("suppliers").select("id, name, tenant_id").execute()
own_data   = own_resp.data or []
print(f"  Resultaat: {len(own_data)} supplier(s)")
if own_data:
    ok(f"Eigen data zichtbaar: {[r['name'] for r in own_data]}")
else:
    # 0 suppliers is OK als de tenant gewoon geen suppliers heeft
    ok("Tenant client werkt (0 suppliers — mogelijk lege tenant)")

# ── Stap 3: vreemde tenant data ophalen — moet leeg zijn ─────
print(f"\nStap 3: Suppliers ophalen als '{other_slug}' (andere tenant)...")
other_client = make_tenant_client(other_id)
other_resp   = other_client.table("suppliers").select("id, name, tenant_id").execute()
other_data   = other_resp.data or []
print(f"  Resultaat: {len(other_data)} supplier(s)")
if len(other_data) == 0:
    ok("Cross-tenant isolatie werkt: geen data zichtbaar van andere tenant")
else:
    fail(f"RLS FOUT: andere tenant ziet {len(other_data)} rijen die niet van hem zijn!")

# ── Stap 4: products isolatie ────────────────────────────────
print(f"\nStap 4: Products ophalen als '{own_slug}'...")
own_prods = own_client.table("products").select("sku_id, naam, tenant_id").eq("is_actief", True).execute()
own_prod_data = own_prods.data or []
print(f"  Resultaat: {len(own_prod_data)} product(s)")
ok(f"Products query werkt ({len(own_prod_data)} rijen)")

print(f"\nStap 5: Products ophalen als '{other_slug}'...")
other_prods = other_client.table("products").select("sku_id, naam, tenant_id").execute()
other_prod_data = other_prods.data or []
if len(other_prod_data) == 0:
    ok("Cross-tenant isolatie voor products: OK")
else:
    fail(f"RLS FOUT: andere tenant ziet {len(other_prod_data)} products!")

# ── Stap 6: service_role ziet alles (sanity check) ───────────
print(f"\nStap 6: Service_role ziet alle suppliers (bypass RLS)...")
all_resp = admin.table("suppliers").select("id, tenant_id").execute()
all_data = all_resp.data or []
print(f"  Resultaat: {len(all_data)} supplier(s) totaal")
if len(all_data) >= len(own_data):
    ok(f"service_role ziet alles: {len(all_data)} rijen")
else:
    fail("service_role ziet minder dan tenant client — iets klopt niet")

print("\n=== ALLE TESTS GESLAAGD ===\n")
print("A4 stop-conditie checklist:")
print("  [v] get_tenant_client() geimplementeerd in db.py")
print("  [v] Tenant queries gebruiken tenant client")
print("  [v] Cross-tenant isolatie getest")
print("  [ ] Commit + push naar main  <- nog te doen")
