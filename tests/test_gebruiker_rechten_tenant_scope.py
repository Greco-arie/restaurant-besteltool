"""
Tests voor tenant-scoped gebruiker-rechten mutatie (STAP 1b-2 — Fase 3.1).

HIGH security fix: `update_gebruiker_rechten` moet tenant-scoped draaien via
`get_tenant_client(tenant_id)` + defense-in-depth `.eq("tenant_id", tenant_id)`.
Voorheen liep de functie via `get_client()` (service_role, RLS bypassed) wat
cross-tenant rechten-wijziging mogelijk maakte.

Dode code `laad_gebruiker_rechten` wordt in dezelfde stap verwijderd (0 callers).

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
    Supabase fluent-chain mock: table() → update() → eq() → eq() → execute().
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
        data_terug = [{"id": "user-1", "tenant_id": "tenant-A"}]

    chain = _maak_query_chain(data_terug)
    client = MagicMock()
    client.table.return_value = chain

    tenant_factory = MagicMock(return_value=client)
    client_factory_oud = MagicMock()

    monkeypatch.setattr("db.get_tenant_client", tenant_factory)
    monkeypatch.setattr("db.get_client", client_factory_oud)

    return tenant_factory, client_factory_oud, chain


# ─── update_gebruiker_rechten ───────────────────────────────────────────────

@pytest.mark.unit
def test_update_gebruiker_rechten_heeft_tenant_id_als_eerste_positional():
    """Contract: tenant_id MOET eerste parameter zijn (consistent met andere tenant-scoped functies)."""
    import db
    params = list(inspect.signature(db.update_gebruiker_rechten).parameters)
    assert params[0] == "tenant_id", f"tenant_id moet eerste param zijn, zag: {params[:3]}"


@pytest.mark.unit
def test_update_gebruiker_rechten_gebruikt_tenant_client_niet_get_client(monkeypatch):
    """Mag NIET via service_role — MOET via get_tenant_client(tenant_id)."""
    import db
    tenant_factory, oud_factory, _ = _mock_tenant_client(monkeypatch)

    ok, _ = db.update_gebruiker_rechten("tenant-A", "user-1", {"mag_bestellen": True})

    assert ok is True
    tenant_factory.assert_called_once_with("tenant-A")
    assert not oud_factory.called, "get_client() mag niet meer gebruikt worden"


@pytest.mark.unit
def test_update_gebruiker_rechten_filter_bevat_id_en_tenant_id(monkeypatch):
    """Defense-in-depth: query MOET zowel .eq('id',...) als .eq('tenant_id',...) bevatten."""
    import db
    _, _, chain = _mock_tenant_client(monkeypatch)

    db.update_gebruiker_rechten("tenant-A", "user-1", {"mag_bestellen": True})

    eq_paren = [(c.args[0], c.args[1]) for c in chain.eq.call_args_list]
    assert ("id", "user-1") in eq_paren, f"Ontbrekend .eq('id',...), zag {eq_paren}"
    assert ("tenant_id", "tenant-A") in eq_paren, f"Ontbrekend .eq('tenant_id',...), zag {eq_paren}"


@pytest.mark.unit
def test_update_gebruiker_rechten_schrijft_naar_tenant_users_tabel(monkeypatch):
    """Tabelkeuze moet tenant_users zijn."""
    import db
    tenant_factory, _, _ = _mock_tenant_client(monkeypatch)

    db.update_gebruiker_rechten("tenant-A", "user-1", {"mag_bestellen": True})

    client = tenant_factory.return_value
    client.table.assert_called_with("tenant_users")


@pytest.mark.unit
def test_update_gebruiker_rechten_geeft_false_bij_nul_rijen_geraakt(monkeypatch):
    """Bij RLS-block / cross-tenant user_id: resp.data == [] → (False, foutmelding)."""
    import db
    _mock_tenant_client(monkeypatch, data_terug=[])

    ok, fout = db.update_gebruiker_rechten("tenant-A", "user-van-b", {"mag_bestellen": True})

    assert ok is False, "Bij 0 rijen geraakt moet ok=False zijn (stille failure voorkomen)"
    assert fout, "Foutmelding mag niet leeg zijn"
    laag = fout.lower()
    assert "niet gevonden" in laag or "geen toegang" in laag, \
        f"Foutmelding moet duiden op niet-gevonden/geen-toegang, kreeg: {fout!r}"


@pytest.mark.unit
@pytest.mark.parametrize("leeg_tenant", ["", None])
def test_update_gebruiker_rechten_weigert_lege_tenant_id(monkeypatch, leeg_tenant):
    """Lege/None tenant_id MOET vroeg bouncen — voorkomt JWT met tenant_id=''."""
    import db
    tenant_factory, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.update_gebruiker_rechten(leeg_tenant, "user-1", {"mag_bestellen": True})

    assert ok is False
    assert "ongeldige tenant" in fout.lower(), f"Moet expliciet weigeren, kreeg: {fout!r}"
    assert not tenant_factory.called, \
        "get_tenant_client mag NIET aangeroepen worden met lege tenant_id"


@pytest.mark.unit
def test_update_gebruiker_rechten_geeft_tuple_terug(monkeypatch):
    """Return is tuple[bool, str] — niet bare bool (regressie op oude signature)."""
    import db
    _mock_tenant_client(monkeypatch)

    resultaat = db.update_gebruiker_rechten("tenant-A", "user-1", {"mag_bestellen": True})

    assert isinstance(resultaat, tuple), f"Moet tuple zijn, kreeg {type(resultaat).__name__}"
    assert len(resultaat) == 2, f"Tuple moet (bool, str) zijn, kreeg lengte {len(resultaat)}"
    assert isinstance(resultaat[0], bool)
    assert isinstance(resultaat[1], str)


@pytest.mark.unit
def test_update_gebruiker_rechten_schrijft_permissions_payload(monkeypatch):
    """Payload MOET exact {'permissions': rechten} zijn — geen lekkende velden."""
    import db
    _, _, chain = _mock_tenant_client(monkeypatch)

    rechten = {"mag_bestellen": True, "mag_rapportages_zien": False}
    db.update_gebruiker_rechten("tenant-A", "user-1", rechten)

    update_calls = chain.update.call_args_list
    assert len(update_calls) == 1, f"Precies 1 .update()-call verwacht, zag {len(update_calls)}"
    payload = update_calls[0].args[0]
    assert payload == {"permissions": rechten}, \
        f"Payload moet alleen 'permissions' bevatten, kreeg: {payload!r}"


# ─── laad_gebruiker_rechten (dode code) ─────────────────────────────────────

@pytest.mark.unit
def test_laad_gebruiker_rechten_is_verwijderd():
    """Dode code (0 callers) moet uit db.py weg — voorkomt onbeveiligd copy-paste hergebruik."""
    import db
    assert not hasattr(db, "laad_gebruiker_rechten"), \
        "laad_gebruiker_rechten was dode code en moet verwijderd zijn uit db.py"
