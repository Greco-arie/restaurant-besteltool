"""
Tests voor tenant-scoped wachtwoord-reset (STAP 1b-3 commit-groep 2 \u2014 Fase 3.1).

HIGH security fix: `reset_wachtwoord` moet tenant-scoped draaien via
`get_tenant_client(tenant_id)` + defense-in-depth `.eq("tenant_id", tenant_id)`.
Voorheen liep de functie via `get_client()` (service_role, RLS bypassed) +
alleen `.eq("id", user_id)`. Cross-tenant wachtwoord-reset was mogelijk als
een attacker een geldige token-hash had (of RPC direct aanriep) en een user_id
van een andere tenant kende.

De reset-token flow is pre-auth: `verifieer_reset_token` verifieert de
token-hash v\u00f3\u00f3r hij `tenant_id` teruggeeft, dus de caller krijgt pas een
tenant_id als de token \u00e9chte houdbaarheid heeft. `get_tenant_client(tenant_id)`
mint dan een JWT voor die specifieke tenant.

Tests zijn @pytest.mark.unit \u2014 geen Supabase nodig.
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest


# \u2500\u2500\u2500 Helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _maak_query_chain(data_terug: list[dict]) -> MagicMock:
    chain = MagicMock()
    for naam in ("update", "eq"):
        getattr(chain, naam).return_value = chain
    execute_resultaat = MagicMock()
    execute_resultaat.data = data_terug
    chain.execute.return_value = execute_resultaat
    return chain


def _mock_tenant_client(monkeypatch, data_terug: list[dict] | None = None):
    """Patch get_tenant_client + get_client. RPC (hash_password) blijft via get_client."""
    if data_terug is None:
        data_terug = [{"id": "user-1", "tenant_id": "tenant-A"}]

    chain = _maak_query_chain(data_terug)
    client = MagicMock()
    client.table.return_value = chain
    rpc_resp = MagicMock()
    rpc_resp.data = "bcrypt-hash-placeholder"
    client.rpc.return_value.execute.return_value = rpc_resp

    tenant_factory = MagicMock(return_value=client)
    client_oud = MagicMock()
    client_oud.rpc.return_value.execute.return_value = rpc_resp
    # Ook .table() geeft een MagicMock zodat we per ongeluk gebruik kunnen detecteren
    client_factory_oud = MagicMock(return_value=client_oud)
    admin_factory_oud = MagicMock(return_value=client_oud)

    monkeypatch.setattr("db.get_tenant_client", tenant_factory)
    monkeypatch.setattr("db.get_client", client_factory_oud)
    monkeypatch.setattr("db.get_admin_client", admin_factory_oud)

    return tenant_factory, client_factory_oud, admin_factory_oud, chain


# \u2500\u2500\u2500 signature & contract \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
def test_reset_wachtwoord_heeft_tenant_id_als_eerste_positional():
    """Contract: tenant_id MOET eerste parameter zijn (consistent met STAP 1b-1/1b-2/1b-3)."""
    import db
    params = list(inspect.signature(db.reset_wachtwoord).parameters)
    assert params[0] == "tenant_id", f"tenant_id moet eerste param zijn, zag: {params[:3]}"


@pytest.mark.unit
def test_reset_wachtwoord_geeft_tuple_terug(monkeypatch):
    """Return is tuple[bool, str] \u2014 consistent met andere tenant-scoped writes."""
    import db
    _mock_tenant_client(monkeypatch)

    resultaat = db.reset_wachtwoord("tenant-A", "user-1", "geheim123")

    assert isinstance(resultaat, tuple)
    assert len(resultaat) == 2
    assert isinstance(resultaat[0], bool)
    assert isinstance(resultaat[1], str)


# \u2500\u2500\u2500 tenant-scoping \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
def test_reset_wachtwoord_gebruikt_tenant_client_voor_update(monkeypatch):
    """De UPDATE op tenant_users MOET via get_tenant_client lopen."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, _ = db.reset_wachtwoord("tenant-A", "user-1", "geheim123")

    assert ok is True
    tenant_factory.assert_called_with("tenant-A")


@pytest.mark.unit
def test_reset_wachtwoord_tenant_users_niet_via_service_role(monkeypatch):
    """De tenant_users UPDATE mag NIET via get_client() of get_admin_client() lopen."""
    import db
    _, oud_factory, admin_factory, _ = _mock_tenant_client(monkeypatch)

    db.reset_wachtwoord("tenant-A", "user-1", "geheim123")

    # get_client() mag WEL voor de hash_password RPC (pure utility),
    # maar NOOIT voor een tenant_users table()-call.
    for factory in (oud_factory, admin_factory):
        if factory.called:
            client = factory.return_value
            table_calls = [c.args for c in client.table.call_args_list]
            assert ("tenant_users",) not in table_calls, \
                f"tenant_users mag niet via service_role \u2014 zag calls: {table_calls}"


@pytest.mark.unit
def test_reset_wachtwoord_filter_bevat_id_en_tenant_id(monkeypatch):
    """Defense-in-depth: filter MOET .eq('id',...) \u00e9n .eq('tenant_id',...) bevatten."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.reset_wachtwoord("tenant-A", "user-1", "geheim123")

    eq_paren = [(c.args[0], c.args[1]) for c in chain.eq.call_args_list]
    assert ("id", "user-1") in eq_paren, f"Ontbrekend .eq('id',...), zag {eq_paren}"
    assert ("tenant_id", "tenant-A") in eq_paren, f"Ontbrekend .eq('tenant_id',...), zag {eq_paren}"


@pytest.mark.unit
def test_reset_wachtwoord_schrijft_password_hash(monkeypatch):
    """Payload MOET {'password': <hash>} zijn, geen andere velden."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.reset_wachtwoord("tenant-A", "user-1", "geheim123")

    update_calls = chain.update.call_args_list
    assert len(update_calls) == 1
    payload = update_calls[0].args[0]
    assert payload == {"password": "bcrypt-hash-placeholder"}, \
        f"Payload moet alleen 'password' bevatten, kreeg: {payload!r}"


# \u2500\u2500\u2500 0-row check (cross-tenant defense) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
def test_reset_wachtwoord_geeft_false_bij_nul_rijen(monkeypatch):
    """Cross-tenant user_id \u2192 RLS blokkeert \u2192 resp.data == [] \u2192 (False, fout)."""
    import db
    _mock_tenant_client(monkeypatch, data_terug=[])

    ok, fout = db.reset_wachtwoord("tenant-A", "user-van-b", "geheim123")

    assert ok is False
    laag = fout.lower()
    assert "niet gevonden" in laag or "geen toegang" in laag, \
        f"Foutmelding moet duiden op niet-gevonden/geen-toegang, kreeg: {fout!r}"


# \u2500\u2500\u2500 empty-guards \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
@pytest.mark.parametrize("leeg_tenant", ["", None])
def test_reset_wachtwoord_weigert_lege_tenant_id(monkeypatch, leeg_tenant):
    """Lege/None tenant_id MOET vroeg bouncen \u2014 voorkomt JWT-mint met lege tenant."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.reset_wachtwoord(leeg_tenant, "user-1", "geheim123")

    assert ok is False
    assert "ongeldige tenant" in fout.lower()
    assert not tenant_factory.called


@pytest.mark.unit
def test_reset_wachtwoord_weigert_lege_user_id(monkeypatch):
    """Lege user_id MOET bouncen \u2014 voorkomt UPDATE zonder id-filter."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.reset_wachtwoord("tenant-A", "", "geheim123")

    assert ok is False
    assert "gebruiker" in fout.lower() or "ongeldig" in fout.lower()
    assert not tenant_factory.called


@pytest.mark.unit
def test_reset_wachtwoord_weigert_leeg_wachtwoord(monkeypatch):
    """Leeg wachtwoord MOET bouncen \u2014 voorkomt dat hash_password een lege string hasht."""
    import db
    tenant_factory, oud_factory, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.reset_wachtwoord("tenant-A", "user-1", "")

    assert ok is False
    assert "wachtwoord" in fout.lower()
    assert not tenant_factory.called
    assert not oud_factory.called, "hash_password RPC mag niet aangeroepen worden bij leeg password"
