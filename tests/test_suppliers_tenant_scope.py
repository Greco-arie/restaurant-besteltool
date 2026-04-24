"""
Tests voor tenant-scoped supplier mutaties (STAP 1b — Fase 3.1).

HIGH security fix: `update_leverancier` en `verwijder_leverancier` moeten
tenant-scoped draaien via `get_tenant_client(tenant_id)` + defense-in-depth
`.eq("tenant_id", tenant_id)`. Voorheen liepen beide via `get_client()`
(service_role, RLS bypassed) wat cross-tenant data-manipulatie mogelijk maakte.

Alle tests hier zijn @pytest.mark.unit — geen Supabase nodig, draaien altijd.
Integration-tests die echt RLS hitten staan in tests/test_rls.py.
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────

def _maak_query_chain(data_terug: list[dict]) -> MagicMock:
    """
    Supabase fluent-chain mock: table() → update()/delete() → eq() → eq() → execute().
    Elke chainstap retourneert dezelfde mock; .execute() geeft een object met .data terug.
    """
    chain = MagicMock()
    for naam in ("update", "delete", "insert", "select", "eq"):
        getattr(chain, naam).return_value = chain
    execute_resultaat = MagicMock()
    execute_resultaat.data = data_terug
    chain.execute.return_value = execute_resultaat
    return chain


def _mock_tenant_client(monkeypatch, data_terug: list[dict] | None = None):
    """
    Patch `db.get_tenant_client` met een mock die de query-chain vastlegt.
    Patch ook `db.get_client` zodat we kunnen bewijzen dat de oude helper niet meer wordt gebruikt.
    Returnt (mock_tenant_factory, mock_client_factory_oud, chain).
    """
    if data_terug is None:
        data_terug = [{"id": "sup-1", "tenant_id": "tenant-A"}]

    chain = _maak_query_chain(data_terug)
    client = MagicMock()
    client.table.return_value = chain

    tenant_factory = MagicMock(return_value=client)
    client_factory_oud = MagicMock()

    monkeypatch.setattr("db.get_tenant_client", tenant_factory)
    monkeypatch.setattr("db.get_client", client_factory_oud)

    return tenant_factory, client_factory_oud, chain


def _geldige_update_args(tenant_id: str = "tenant-A", supplier_id: str = "sup-1") -> tuple:
    """Handige default args voor update_leverancier."""
    return (
        tenant_id, supplier_id,
        "Naam Leverancier", "bestel@x.nl", "Beste leverancier,", 1,
        True, True, True, True, True, False, False,
    )


# ─── update_leverancier ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_update_leverancier_heeft_tenant_id_als_eerste_positional():
    """Contract: tenant_id MOET eerste parameter zijn (consistent met voeg_leverancier_toe)."""
    import db
    params = list(inspect.signature(db.update_leverancier).parameters)
    assert params[0] == "tenant_id", f"tenant_id moet eerste param zijn, zag: {params[:3]}"


@pytest.mark.unit
def test_update_leverancier_gebruikt_tenant_client_niet_get_client(monkeypatch):
    """Mag NIET via service_role — MOET via get_tenant_client(tenant_id)."""
    import db
    tenant_factory, oud_factory, _ = _mock_tenant_client(monkeypatch)

    ok, _ = db.update_leverancier(*_geldige_update_args())

    assert ok is True
    tenant_factory.assert_called_once_with("tenant-A")
    assert not oud_factory.called, "get_client() mag niet meer gebruikt worden"


@pytest.mark.unit
def test_update_leverancier_filter_bevat_id_en_tenant_id(monkeypatch):
    """Defense-in-depth: query MOET zowel .eq('id',...) als .eq('tenant_id',...) bevatten."""
    import db
    _, _, chain = _mock_tenant_client(monkeypatch)

    db.update_leverancier(*_geldige_update_args())

    eq_paren = [(c.args[0], c.args[1]) for c in chain.eq.call_args_list]
    assert ("id", "sup-1") in eq_paren, f"Ontbrekend .eq('id',...), zag {eq_paren}"
    assert ("tenant_id", "tenant-A") in eq_paren, f"Ontbrekend .eq('tenant_id',...), zag {eq_paren}"


@pytest.mark.unit
def test_update_leverancier_geeft_false_bij_nul_rijen_geraakt(monkeypatch):
    """Bij RLS-block / cross-tenant supplier_id: resp.data == [] → (False, foutmelding)."""
    import db
    _mock_tenant_client(monkeypatch, data_terug=[])

    ok, fout = db.update_leverancier(*_geldige_update_args())

    assert ok is False, "Bij 0 rijen geraakt moet ok=False zijn (stille failure voorkomen)"
    assert fout, "Foutmelding mag niet leeg zijn"
    laag = fout.lower()
    assert "niet gevonden" in laag or "geen toegang" in laag, \
        f"Foutmelding moet duiden op niet-gevonden/geen-toegang, kreeg: {fout!r}"


@pytest.mark.unit
def test_update_leverancier_schrijft_naar_suppliers_tabel(monkeypatch):
    """Tabelkeuze mag niet veranderen door de refactor."""
    import db
    tenant_factory, _, _ = _mock_tenant_client(monkeypatch)

    db.update_leverancier(*_geldige_update_args())

    client = tenant_factory.return_value
    client.table.assert_called_with("suppliers")


@pytest.mark.unit
@pytest.mark.parametrize("leeg_tenant", ["", None])
def test_update_leverancier_weigert_lege_tenant_id(monkeypatch, leeg_tenant):
    """Lege/None tenant_id MOET vroeg bouncen — voorkomt JWT met tenant_id=''."""
    import db
    tenant_factory, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.update_leverancier(
        leeg_tenant, "sup-1",
        "Naam", "e@x.nl", "Aanhef", 1,
        True, True, True, True, True, False, False,
    )

    assert ok is False
    assert "ongeldige tenant" in fout.lower(), f"Moet expliciet weigeren, kreeg: {fout!r}"
    assert not tenant_factory.called, \
        "get_tenant_client mag NIET aangeroepen worden met lege tenant_id"


# ─── verwijder_leverancier ──────────────────────────────────────────────────

@pytest.mark.unit
def test_verwijder_leverancier_heeft_tenant_id_als_eerste_positional():
    import db
    params = list(inspect.signature(db.verwijder_leverancier).parameters)
    assert params[0] == "tenant_id", f"tenant_id moet eerste param zijn, zag: {params}"


@pytest.mark.unit
def test_verwijder_leverancier_gebruikt_tenant_client_niet_get_client(monkeypatch):
    import db
    tenant_factory, oud_factory, _ = _mock_tenant_client(monkeypatch)

    ok, _ = db.verwijder_leverancier("tenant-A", "sup-1")

    assert ok is True
    tenant_factory.assert_called_once_with("tenant-A")
    oud_factory.assert_not_called()


@pytest.mark.unit
def test_verwijder_leverancier_filter_bevat_id_en_tenant_id(monkeypatch):
    import db
    _, _, chain = _mock_tenant_client(monkeypatch)

    db.verwijder_leverancier("tenant-A", "sup-1")

    eq_paren = [(c.args[0], c.args[1]) for c in chain.eq.call_args_list]
    assert ("id", "sup-1") in eq_paren
    assert ("tenant_id", "tenant-A") in eq_paren


@pytest.mark.unit
def test_verwijder_leverancier_geeft_false_bij_nul_rijen(monkeypatch):
    """Cross-tenant delete-poging → 0 rijen geraakt → expliciete fout."""
    import db
    _mock_tenant_client(monkeypatch, data_terug=[])

    ok, fout = db.verwijder_leverancier("tenant-A", "sup-van-b")

    assert ok is False
    laag = fout.lower()
    assert "niet gevonden" in laag or "geen toegang" in laag, \
        f"Foutmelding moet duiden op niet-gevonden/geen-toegang, kreeg: {fout!r}"


@pytest.mark.unit
def test_verwijder_leverancier_doet_soft_delete(monkeypatch):
    """Verwijder = soft delete (is_active=False), geen echte DELETE."""
    import db
    _, _, chain = _mock_tenant_client(monkeypatch)

    db.verwijder_leverancier("tenant-A", "sup-1")

    # .update({"is_active": False}) moet aangeroepen zijn, .delete() niet
    update_calls = chain.update.call_args_list
    assert any(
        isinstance(c.args[0], dict) and c.args[0].get("is_active") is False
        for c in update_calls
    ), f"Moet update({{'is_active': False}}) zijn, zag: {update_calls}"
    assert not chain.delete.called, "Soft delete, dus geen .delete() aanroep"
