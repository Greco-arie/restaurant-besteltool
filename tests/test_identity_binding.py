"""
Tests voor HMAC identity-binding (STAP 1b-4 — Fase 3.1).

HIGH security fix: `get_tenant_client(tenant_id)` moet cryptografisch verifiëren
dat de opgegeven `tenant_id` bij de ingelogde gebruiker hoort — zonder DB-roundtrip
en zonder te vertrouwen op muteerbare session_state-velden.

Ontwerp (Optie A):
  identity_proof = HMAC-SHA256(jwt_secret, f"{tenant_id}|{username}").hexdigest()

- `verificeer_gebruiker` berekent de proof en geeft hem terug in de response-dict.
- `UserSession` bevat `identity_proof` als verplicht, frozen veld.
- `state.set_user` schrijft de proof naar session_state (legacy key `identity_proof`).
- `get_tenant_client(tenant_id)`:
    1. Lees `username` + `identity_proof` uit session_state.
    2. Ontbreekt → RuntimeError + audit-log `identity_binding_ontbreekt`.
    3. Recompute expected HMAC op (tenant_id, username) met jwt_secret.
    4. `hmac.compare_digest(expected, stored)` — mismatch → audit-log
       `identity_binding_mismatch` + RuntimeError.
    5. Alleen bij match: huidige JWT-mint flow.

Tests zijn @pytest.mark.unit — geen Supabase nodig.
"""
from __future__ import annotations

import hashlib
import hmac
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import streamlit as st


# ── Helpers ────────────────────────────────────────────────────────────────

def _bereken_expected_proof(tenant_id: str, username: str, secret: str) -> str:
    """Spiegel van de productie-berekening — gebruikt in de testverwachtingen."""
    return hmac.new(
        secret.encode(),
        f"{tenant_id}|{username}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _mock_verificeer_login_rpc(monkeypatch, user_rij: dict):
    """Patch db.get_client zodat verificeer_login RPC de gegeven rij teruggeeft."""
    rpc_resp = MagicMock()
    rpc_resp.data = [user_rij]
    client = MagicMock()
    client.rpc.return_value.execute.return_value = rpc_resp
    monkeypatch.setattr("db.get_client", MagicMock(return_value=client))
    return client


def _reset_session_state():
    """Legacy-keys opruimen tussen tests — st.session_state is een singleton."""
    for k in ("user_session", "ingelogd", "tenant_id", "tenant_naam",
              "user_naam", "user_rol", "user_permissions", "identity_proof"):
        st.session_state.pop(k, None)


@pytest.fixture(autouse=True)
def _clean_session_state():
    _reset_session_state()
    yield
    _reset_session_state()


# ── 1. verificeer_gebruiker bevat identity_proof ──────────────────────────

@pytest.mark.unit
def test_verificeer_gebruiker_bevat_identity_proof(monkeypatch):
    """Na een geslaagde login MOET de retour-dict een identity_proof bevatten."""
    import db

    _mock_verificeer_login_rpc(monkeypatch, {
        "tenant_id":   "tenant-A",
        "tenant_naam": "Family Maarssen",
        "username":    "manager",
        "role":        "manager",
        "full_name":   "Jan de Manager",
        "permissions": {"closing_invoeren": True},
    })

    resultaat = db.verificeer_gebruiker("family", "manager", "geheim123")

    assert resultaat is not None, "Login moet slagen in deze test"
    assert "identity_proof" in resultaat, (
        "verificeer_gebruiker MOET identity_proof in retour-dict zetten"
    )
    verwacht = _bereken_expected_proof(
        "tenant-A", "manager", st.secrets["supabase"]["jwt_secret"]
    )
    assert resultaat["identity_proof"] == verwacht


# ── 2. HMAC is deterministisch ────────────────────────────────────────────

@pytest.mark.unit
def test_identity_proof_is_deterministisch(monkeypatch):
    """Zelfde (tenant_id, username, secret) → zelfde proof, elke keer."""
    import db

    user_rij = {
        "tenant_id":   "tenant-B",
        "tenant_naam": "Bistro B",
        "username":    "alice",
        "role":        "user",
        "full_name":   "Alice",
        "permissions": {},
    }
    _mock_verificeer_login_rpc(monkeypatch, user_rij)

    eerste  = db.verificeer_gebruiker("bistro-b", "alice", "pw")
    tweede  = db.verificeer_gebruiker("bistro-b", "alice", "pw")

    assert eerste is not None and tweede is not None
    assert eerste["identity_proof"] == tweede["identity_proof"], (
        "HMAC moet deterministisch zijn voor dezelfde input"
    )
    # En sanity: verschillende username geeft andere proof
    andere_rij = {**user_rij, "username": "bob"}
    _mock_verificeer_login_rpc(monkeypatch, andere_rij)
    derde = db.verificeer_gebruiker("bistro-b", "bob", "pw")
    assert derde is not None
    assert derde["identity_proof"] != eerste["identity_proof"]


# ── 3. get_tenant_client accepteert geldige binding ───────────────────────

@pytest.mark.unit
def test_get_tenant_client_accepteert_geldige_binding():
    """Happy path: username + correcte proof in session_state → JWT wordt gemunt."""
    import db

    tenant_id = "tenant-A"
    username  = "manager"
    secret    = st.secrets["supabase"]["jwt_secret"]
    st.session_state["user_naam"]       = username
    st.session_state["identity_proof"]  = _bereken_expected_proof(
        tenant_id, username, secret
    )

    client = db.get_tenant_client(tenant_id)

    assert client is not None, "Geldige binding moet een Supabase client teruggeven"


# ── 4. get_tenant_client weigert gemanipuleerde tenant_id ─────────────────

@pytest.mark.unit
def test_get_tenant_client_weigert_gemanipuleerde_tenant_id(monkeypatch):
    """Aanvaller zet andere tenant_id in session_state → RuntimeError + audit-log."""
    import db

    echte_tenant   = "tenant-A"
    aanval_tenant  = "tenant-EVIL"
    username       = "manager"
    secret         = st.secrets["supabase"]["jwt_secret"]

    # Proof is voor de échte tenant; aanvaller vraagt client voor andere tenant.
    st.session_state["user_naam"]      = username
    st.session_state["identity_proof"] = _bereken_expected_proof(
        echte_tenant, username, secret
    )

    audit_calls: list[tuple] = []
    def _fake_audit(tid, uname, actie, details=None):
        audit_calls.append((tid, uname, actie, details))
    monkeypatch.setattr("audit.log_audit_event", _fake_audit)

    with pytest.raises(RuntimeError):
        db.get_tenant_client(aanval_tenant)

    assert any(c[2] == "identity_binding_mismatch" for c in audit_calls), (
        f"Audit-log moet 'identity_binding_mismatch' bevatten, zag: {audit_calls}"
    )


# ── 5. get_tenant_client weigert ontbrekende proof ────────────────────────

@pytest.mark.unit
def test_get_tenant_client_weigert_ontbrekende_proof(monkeypatch):
    """Zonder identity_proof in session_state → RuntimeError + audit-log."""
    import db

    st.session_state["user_naam"] = "manager"
    # BEWUST: geen identity_proof in session_state.

    audit_calls: list[tuple] = []
    def _fake_audit(tid, uname, actie, details=None):
        audit_calls.append((tid, uname, actie, details))
    monkeypatch.setattr("audit.log_audit_event", _fake_audit)

    with pytest.raises(RuntimeError):
        db.get_tenant_client("tenant-A")

    assert any(c[2] == "identity_binding_ontbreekt" for c in audit_calls), (
        f"Audit-log moet 'identity_binding_ontbreekt' bevatten, zag: {audit_calls}"
    )


# ── 6. HMAC-vergelijking gebruikt compare_digest ──────────────────────────

@pytest.mark.unit
def test_hmac_vergelijking_gebruikt_compare_digest():
    """
    Source-scan: de binding-check MOET hmac.compare_digest gebruiken, niet ==.

    Timing-safe vergelijking is essentieel bij een geheim-afhankelijke HMAC;
    een naive == kan via timing-side-channels lekken. De check is inmiddels
    verhuisd naar auth_binding.verifieer_binding_of_raise zodat db.py onder
    de 800-regel grens blijft.
    """
    import auth_binding
    bron = Path(inspect.getsourcefile(auth_binding.verifieer_binding_of_raise)).read_text(encoding="utf-8")
    start = bron.find("def verifieer_binding_of_raise(")
    assert start != -1, "verifieer_binding_of_raise niet gevonden in bron"
    volgende_def = bron.find("\ndef ", start + 1)
    body = bron[start:volgende_def if volgende_def != -1 else None]
    assert "compare_digest" in body, (
        "verifieer_binding_of_raise MOET hmac.compare_digest gebruiken"
    )
    assert " == " not in body.replace("!= ", ""), (
        "Geen naive == vergelijking op proofs in verifieer_binding_of_raise"
    )
