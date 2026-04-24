"""
Tests voor Row-Level-Security via JWT (Fase 3.1).

Twee lagen:
  1. Unit-tests (@pytest.mark.unit) — JWT-payload inspection, zonder Supabase.
     Draaien altijd, ook in CI zonder secrets.
  2. Integration-tests (@pytest.mark.integration) — hitten live Supabase met
     2 test-tenants en bewijzen dat tenant A geen data van tenant B kan zien.
     Vereisen RLS_TEST_ENABLED=1 + .env.test; gesupt in conftest.py.

Integration-tests maken zelf een tweede test-tenant aan (via get_admin_client),
seeden één supplier, en ruimen na afloop alles op in een try/finally.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import jwt as pyjwt
import pytest
import streamlit as st

from auth_binding import bereken_identity_proof


def _seed_identity_binding(tenant_id: str, username: str = "manager") -> None:
    """Zet een geldige HMAC-binding in session_state voor get_tenant_client."""
    st.session_state["user_naam"]      = username
    st.session_state["identity_proof"] = bereken_identity_proof(
        tenant_id, username, st.secrets["supabase"]["jwt_secret"]
    )


def _clear_identity_binding() -> None:
    for k in ("user_naam", "identity_proof"):
        st.session_state.pop(k, None)


# ═══════════════════════════════════════════════════════════════════════════
# UNIT TESTS — geen Supabase, geen secrets nodig
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
def test_tenant_client_bevat_jwt_met_correcte_claims():
    """
    JWT in Authorization-header moet: role=authenticated, tenant_id=arg, iss=supabase.
    Zonder deze claims werken v12-policies niet (tenant_jwt_id() returnt null).
    """
    from db import get_tenant_client

    tenant_id = str(uuid.uuid4())
    _seed_identity_binding(tenant_id)
    try:
        client = get_tenant_client(tenant_id)
    finally:
        _clear_identity_binding()

    auth_header = client.options.headers.get("Authorization", "")
    assert auth_header.startswith("Bearer "), "Authorization-header moet Bearer-token bevatten"
    token = auth_header.removeprefix("Bearer ")

    jwt_secret = st.secrets["supabase"]["jwt_secret"]
    payload = pyjwt.decode(token, jwt_secret, algorithms=["HS256"])

    assert payload["role"] == "authenticated", "role claim moet authenticated zijn"
    assert payload["tenant_id"] == tenant_id,   "tenant_id claim moet overeenkomen met argument"
    assert payload["iss"] == "supabase",        "iss claim moet supabase zijn"
    assert payload["sub"] == tenant_id,         "sub claim moet tenant_id zijn (voor auth.uid())"


@pytest.mark.unit
def test_tenant_client_jwt_heeft_exp_ongeveer_1u():
    """JWT moet 1u geldig zijn — niet te kort (sessie-afbreuk), niet te lang (security)."""
    from db import get_tenant_client

    tenant_id = str(uuid.uuid4())
    _seed_identity_binding(tenant_id)
    try:
        client = get_tenant_client(tenant_id)
    finally:
        _clear_identity_binding()
    token = client.options.headers["Authorization"].removeprefix("Bearer ")
    payload = pyjwt.decode(token, st.secrets["supabase"]["jwt_secret"], algorithms=["HS256"])

    geldigheid = payload["exp"] - payload["iat"]
    assert 3500 <= geldigheid <= 3700, f"JWT geldigheid moet ~3600s zijn, is {geldigheid}s"

    # iat mag niet in de toekomst of ver in verleden liggen
    nu = int(datetime.now(timezone.utc).timestamp())
    assert abs(nu - payload["iat"]) <= 5, "iat moet dicht bij nu liggen"


@pytest.mark.unit
def test_tenant_client_niet_gecached_genereert_verse_jwt():
    """
    Twee opeenvolgende calls met zelfde tenant_id moeten twee verschillende JWTs
    opleveren (verschillende iat). Cachen zou tot een expired token kunnen leiden.
    """
    from db import get_tenant_client
    import time

    tenant_id = str(uuid.uuid4())
    _seed_identity_binding(tenant_id)
    try:
        c1 = get_tenant_client(tenant_id)
        time.sleep(1.1)  # iat is in hele seconden, zorg voor verschil
        c2 = get_tenant_client(tenant_id)
    finally:
        _clear_identity_binding()

    token1 = c1.options.headers["Authorization"].removeprefix("Bearer ")
    token2 = c2.options.headers["Authorization"].removeprefix("Bearer ")
    assert token1 != token2, "Tokens moeten vers zijn per call — niet gecached"


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — live Supabase, 2 test-tenants
# ═══════════════════════════════════════════════════════════════════════════

TENANT_TABELLEN = [
    "suppliers",
    "products",
    "sent_emails",
    "sales_history",
    "stock_count",
    "forecast_log",
    "current_inventory",
    "inventory_adjustments",
    "daily_usage",
]


def _check_integration_secrets() -> None:
    """Skip als echte Supabase-secrets ontbreken."""
    for var in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_JWT_SECRET"):
        if not os.environ.get(var) or os.environ[var].startswith("dummy"):
            pytest.skip(f"{var} niet gezet in .env.test")


@pytest.fixture(scope="module")
def test_tenants():
    """
    Maak 2 tijdelijke test-tenants aan via service_role, seed 1 supplier per tenant,
    yield (tenant_a_id, tenant_b_id), en ruim daarna op.
    """
    _check_integration_secrets()
    from db import get_admin_client

    admin = get_admin_client()
    suffix = uuid.uuid4().hex[:8]
    tenant_a = admin.table("tenants").insert(
        {"name": f"rls_test_alpha_{suffix}", "slug": f"rls-test-alpha-{suffix}"}
    ).execute().data[0]
    tenant_b = admin.table("tenants").insert(
        {"name": f"rls_test_beta_{suffix}",  "slug": f"rls-test-beta-{suffix}"}
    ).execute().data[0]

    # Seed: één supplier per tenant
    admin.table("suppliers").insert({
        "tenant_id": tenant_a["id"], "name": f"LevA_{suffix}", "email": "a@test.nl",
        "aanhef": "Test", "lead_time_days": 1, "is_active": True,
    }).execute()
    admin.table("suppliers").insert({
        "tenant_id": tenant_b["id"], "name": f"LevB_{suffix}", "email": "b@test.nl",
        "aanhef": "Test", "lead_time_days": 1, "is_active": True,
    }).execute()

    try:
        yield tenant_a["id"], tenant_b["id"]
    finally:
        # Opruimen — suppliers cascade via ON DELETE, maar doen het expliciet voor de zekerheid
        admin.table("suppliers").delete().eq("tenant_id", tenant_a["id"]).execute()
        admin.table("suppliers").delete().eq("tenant_id", tenant_b["id"]).execute()
        admin.table("tenants").delete().eq("id", tenant_a["id"]).execute()
        admin.table("tenants").delete().eq("id", tenant_b["id"]).execute()


@pytest.mark.integration
def test_tenant_a_ziet_geen_suppliers_van_tenant_b(test_tenants):
    """Rooktest: cliënt van tenant A mag GEEN rij van tenant B ontvangen."""
    from db import get_tenant_client

    tenant_a_id, tenant_b_id = test_tenants
    client_a = get_tenant_client(tenant_a_id)
    resp = client_a.table("suppliers").select("tenant_id").execute()
    tenants_in_resultaat = {row["tenant_id"] for row in (resp.data or [])}
    assert tenant_b_id not in tenants_in_resultaat, \
        f"RLS FAAL: cliënt A ziet rijen van tenant B! Gezien: {tenants_in_resultaat}"


@pytest.mark.integration
def test_tenant_a_ziet_wel_eigen_suppliers(test_tenants):
    """Cliënt van tenant A moet wel z'n eigen seed-data kunnen lezen."""
    from db import get_tenant_client

    tenant_a_id, _ = test_tenants
    client_a = get_tenant_client(tenant_a_id)
    resp = client_a.table("suppliers").select("tenant_id").execute()
    assert resp.data, "Cliënt A moet eigen seed-supplier kunnen lezen"
    assert all(row["tenant_id"] == tenant_a_id for row in resp.data), \
        "Alle rijen moeten tenant_a_id hebben"


@pytest.mark.integration
def test_ontbrekende_tenant_claim_geeft_nul_rijen(test_tenants):
    """
    JWT zonder tenant_id claim → tenant_jwt_id() = null → geen rijen.
    Dit test dat een gecompromitteerde/corrupte client niet álle data dumpt.
    """
    import streamlit as st
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions

    url        = st.secrets["supabase"]["url"]
    anon_key   = st.secrets["supabase"]["anon_key"]
    jwt_secret = st.secrets["supabase"]["jwt_secret"]

    nu = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss":  "supabase",
        "role": "authenticated",
        "iat":  nu,
        "exp":  nu + 3600,
        # geen tenant_id claim
    }
    token = pyjwt.encode(payload, jwt_secret, algorithm="HS256")
    client = create_client(
        url, anon_key,
        options=SyncClientOptions(headers={"Authorization": f"Bearer {token}"}),
    )
    resp = client.table("suppliers").select("tenant_id").execute()
    assert resp.data == [] or resp.data is None, \
        f"JWT zonder tenant_id moet 0 rijen geven, kreeg {len(resp.data or [])}"


@pytest.mark.integration
@pytest.mark.parametrize("tabel", TENANT_TABELLEN)
def test_rls_respect_per_tabel(test_tenants, tabel):
    """
    Voor elk van de 9 tenant-tabellen: cliënt A mag geen tenant_id van B zien.
    Werkt ook als tabel leeg is voor tenant B — dan is resultaat vacuously true.
    """
    from db import get_tenant_client

    tenant_a_id, tenant_b_id = test_tenants
    client_a = get_tenant_client(tenant_a_id)
    resp = client_a.table(tabel).select("tenant_id").execute()
    assert all(row["tenant_id"] == tenant_a_id for row in (resp.data or [])), \
        f"RLS FAAL op tabel {tabel}: cliënt A ziet vreemde tenant_ids"
