"""
Tests voor tenant-scoped gebruikersbeheer-mutaties (STAP 1b-3 \u2014 Fase 3.1).

HIGH security fix: `update_gebruiker` en `verwijder_gebruiker` moeten tenant-scoped
draaien via `get_tenant_client(tenant_id)` + defense-in-depth `.eq("tenant_id", ...)`.
Voorheen liepen deze functies via `get_client()` (service_role, RLS bypassed) wat
cross-tenant UPDATE/DELETE op `tenant_users` mogelijk maakte \u2014 HIGH blast-radius
(privilege-escalatie, cross-tenant user wipe).

Tevens: nieuwe helper `laad_tenant_gebruikers(tenant_id)` wordt toegevoegd voor
de tenant-admin UI (page_instellingen). `laad_alle_gebruikers()` blijft bestaan
voor de super_admin UI (page_admin) en mag cross-tenant zijn.

Alle tests hier zijn @pytest.mark.unit \u2014 geen Supabase nodig.
Patroon is identiek aan tests/test_gebruiker_rechten_tenant_scope.py (STAP 1b-2).
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest


# \u2500\u2500\u2500 Helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _maak_query_chain(data_terug: list[dict]) -> MagicMock:
    """Supabase fluent-chain mock: elke chainstap retourneert dezelfde mock."""
    chain = MagicMock()
    for naam in ("update", "delete", "insert", "select", "eq", "order"):
        getattr(chain, naam).return_value = chain
    execute_resultaat = MagicMock()
    execute_resultaat.data = data_terug
    chain.execute.return_value = execute_resultaat
    return chain


def _mock_tenant_client(monkeypatch, data_terug: list[dict] | None = None):
    """
    Patch `db.get_tenant_client` met een mock. Patch ook `db.get_client` en
    `db.get_admin_client` zodat we kunnen bewijzen dat oude service_role-helpers
    niet meer worden gebruikt voor de table()-call.

    Returnt (tenant_factory, client_factory_oud, admin_factory_oud, chain).
    """
    if data_terug is None:
        data_terug = [{"id": "user-1", "tenant_id": "tenant-A"}]

    chain = _maak_query_chain(data_terug)
    client = MagicMock()
    client.table.return_value = chain
    # rpc() wordt gebruikt voor hash_password \u2014 geen table-access, OK via service_role
    rpc_resp = MagicMock()
    rpc_resp.data = "bcrypt-hash-placeholder"
    client.rpc.return_value.execute.return_value = rpc_resp

    tenant_factory = MagicMock(return_value=client)
    client_oud = MagicMock()
    client_oud.rpc.return_value.execute.return_value = rpc_resp  # hash_password mag via service_role
    client_factory_oud = MagicMock(return_value=client_oud)
    admin_factory_oud = MagicMock(return_value=client_oud)

    monkeypatch.setattr("db.get_tenant_client", tenant_factory)
    monkeypatch.setattr("db.get_client", client_factory_oud)
    monkeypatch.setattr("db.get_admin_client", admin_factory_oud)

    return tenant_factory, client_factory_oud, admin_factory_oud, chain


# \u2500\u2500\u2500 update_gebruiker \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
def test_update_gebruiker_heeft_tenant_id_als_eerste_positional():
    """Contract: tenant_id MOET eerste parameter zijn (consistent met andere tenant-scoped functies)."""
    import db
    params = list(inspect.signature(db.update_gebruiker).parameters)
    assert params[0] == "tenant_id", f"tenant_id moet eerste param zijn, zag: {params[:3]}"


@pytest.mark.unit
def test_update_gebruiker_gebruikt_tenant_client_voor_update(monkeypatch):
    """Mag NIET via service_role voor de UPDATE \u2014 MOET via get_tenant_client(tenant_id)."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, _ = db.update_gebruiker(
        "tenant-A", "user-1", "nieuwe_naam", "Volledige Naam", "manager",
    )

    assert ok is True
    tenant_factory.assert_called_with("tenant-A")


@pytest.mark.unit
def test_update_gebruiker_doet_geen_table_call_via_get_client(monkeypatch):
    """De tenant_users UPDATE mag NIET via get_client().table() lopen."""
    import db
    _, oud_factory, admin_factory, _ = _mock_tenant_client(monkeypatch)

    db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", "manager",
    )

    # get_client() mag WEL worden aangeroepen (voor hash_password RPC indien password gezet),
    # maar hier zetten we geen password \u2014 dus helemaal niet.
    # De tenant_users table-access mag NOOIT via get_client of get_admin_client lopen.
    for factory in (oud_factory, admin_factory):
        if factory.called:
            client = factory.return_value
            table_calls = [c.args for c in client.table.call_args_list]
            assert ("tenant_users",) not in table_calls, \
                f"tenant_users mag niet via service_role \u2014 zag calls: {table_calls}"


@pytest.mark.unit
def test_update_gebruiker_filter_bevat_id_en_tenant_id(monkeypatch):
    """Defense-in-depth: query MOET zowel .eq('id',...) als .eq('tenant_id',...) bevatten."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", "manager",
    )

    eq_paren = [(c.args[0], c.args[1]) for c in chain.eq.call_args_list]
    assert ("id", "user-1") in eq_paren, f"Ontbrekend .eq('id',...), zag {eq_paren}"
    assert ("tenant_id", "tenant-A") in eq_paren, f"Ontbrekend .eq('tenant_id',...), zag {eq_paren}"


@pytest.mark.unit
def test_update_gebruiker_geeft_false_bij_nul_rijen_geraakt(monkeypatch):
    """Cross-tenant user_id \u2192 RLS blokkeert \u2192 resp.data == [] \u2192 (False, foutmelding)."""
    import db
    _mock_tenant_client(monkeypatch, data_terug=[])

    ok, fout = db.update_gebruiker(
        "tenant-A", "user-van-b", "uname", "Volledige Naam", "manager",
    )

    assert ok is False
    assert fout, "Foutmelding mag niet leeg zijn"
    laag = fout.lower()
    assert "niet gevonden" in laag or "geen toegang" in laag, \
        f"Foutmelding moet duiden op niet-gevonden/geen-toegang, kreeg: {fout!r}"


@pytest.mark.unit
@pytest.mark.parametrize("leeg_tenant", ["", None])
def test_update_gebruiker_weigert_lege_tenant_id(monkeypatch, leeg_tenant):
    """Lege/None tenant_id MOET vroeg bouncen \u2014 voorkomt JWT met tenant_id=''."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.update_gebruiker(
        leeg_tenant, "user-1", "uname", "Volledige Naam", "manager",
    )

    assert ok is False
    assert "ongeldige tenant" in fout.lower(), f"Moet expliciet weigeren, kreeg: {fout!r}"
    assert not tenant_factory.called, \
        "get_tenant_client mag NIET aangeroepen worden met lege tenant_id"


@pytest.mark.unit
def test_update_gebruiker_geeft_tuple_terug(monkeypatch):
    """Return is tuple[bool, str] \u2014 niet bare bool (regressie op signature)."""
    import db
    _mock_tenant_client(monkeypatch)

    resultaat = db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", "manager",
    )

    assert isinstance(resultaat, tuple)
    assert len(resultaat) == 2
    assert isinstance(resultaat[0], bool)
    assert isinstance(resultaat[1], str)


@pytest.mark.unit
def test_update_gebruiker_schrijft_basis_velden(monkeypatch):
    """Payload MOET minimaal username, full_name, role bevatten."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.update_gebruiker(
        "tenant-A", "user-1", "nieuwe_uname", "Nieuwe Naam", "admin",
    )

    update_calls = chain.update.call_args_list
    assert len(update_calls) == 1
    payload = update_calls[0].args[0]
    assert payload["username"] == "nieuwe_uname"
    assert payload["full_name"] == "Nieuwe Naam"
    assert payload["role"] == "admin"


@pytest.mark.unit
def test_update_gebruiker_schrijft_password_hash_bij_nieuw_password(monkeypatch):
    """Als password meegegeven, MOET een gehashte waarde in payload staan (via hash_password RPC)."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", "manager",
        password="geheim123",
    )

    payload = chain.update.call_args_list[0].args[0]
    assert "password" in payload, "password-veld moet in payload zitten bij nieuw wachtwoord"
    assert payload["password"] == "bcrypt-hash-placeholder", \
        f"password moet gehashte waarde zijn, kreeg: {payload['password']!r}"


@pytest.mark.unit
@pytest.mark.parametrize("ongeldige_rol", ["super_admin", "root", "", "Admin"])
def test_update_gebruiker_weigert_niet_whitelisted_rol(monkeypatch, ongeldige_rol):
    """Defense-in-depth: backend MOET role-whitelist afdwingen \u2014 UI-check is niet enige bewaking."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", ongeldige_rol,
    )

    assert ok is False, f"Rol {ongeldige_rol!r} zou geweigerd moeten worden"
    assert "rol" in fout.lower()
    assert not tenant_factory.called, \
        "Backend moet vroeg bouncen \u2014 geen JWT-mint voor ongeldige rol"


@pytest.mark.unit
@pytest.mark.parametrize("geldige_rol", ["user", "manager", "admin"])
def test_update_gebruiker_accepteert_geldige_rollen(monkeypatch, geldige_rol):
    """Regressie: de 3 geldige rollen moeten doorgelaten worden."""
    import db
    _mock_tenant_client(monkeypatch)

    ok, _ = db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", geldige_rol,
    )

    assert ok is True


@pytest.mark.unit
def test_update_gebruiker_weigert_lege_user_id(monkeypatch):
    """Empty-guard op user_id \u2014 voorkomt DELETE/UPDATE zonder id-filter."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.update_gebruiker(
        "tenant-A", "", "uname", "Volledige Naam", "manager",
    )

    assert ok is False
    assert "gebruiker" in fout.lower() or "ongeldig" in fout.lower()
    assert not tenant_factory.called


@pytest.mark.unit
def test_update_gebruiker_email_wordt_lowercase_en_getrimd(monkeypatch):
    """email MOET lowercase + strip \u2014 regressie."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", "manager",
        email="  Test@Example.COM  ",
    )

    payload = chain.update.call_args_list[0].args[0]
    assert payload["email"] == "test@example.com"


@pytest.mark.unit
def test_update_gebruiker_email_leeg_wordt_none(monkeypatch):
    """Lege email-string MOET None worden (database-constraint)."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.update_gebruiker(
        "tenant-A", "user-1", "uname", "Volledige Naam", "manager",
        email="   ",
    )

    payload = chain.update.call_args_list[0].args[0]
    assert payload["email"] is None


# \u2500\u2500\u2500 verwijder_gebruiker \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
def test_verwijder_gebruiker_heeft_tenant_id_als_eerste_positional():
    """Contract: tenant_id MOET eerste parameter zijn."""
    import db
    params = list(inspect.signature(db.verwijder_gebruiker).parameters)
    assert params[0] == "tenant_id", f"tenant_id moet eerste param zijn, zag: {params[:3]}"


@pytest.mark.unit
def test_verwijder_gebruiker_gebruikt_tenant_client_niet_get_client(monkeypatch):
    """Mag NIET via service_role \u2014 MOET via get_tenant_client(tenant_id)."""
    import db
    tenant_factory, oud_factory, admin_factory, _ = _mock_tenant_client(monkeypatch)

    ok, _ = db.verwijder_gebruiker("tenant-A", "user-1")

    assert ok is True
    tenant_factory.assert_called_with("tenant-A")
    for factory in (oud_factory, admin_factory):
        if factory.called:
            client = factory.return_value
            table_calls = [c.args for c in client.table.call_args_list]
            assert ("tenant_users",) not in table_calls


@pytest.mark.unit
def test_verwijder_gebruiker_filter_bevat_id_en_tenant_id(monkeypatch):
    """Defense-in-depth: filter MOET id \u00e9n tenant_id bevatten."""
    import db
    _, _, _, chain = _mock_tenant_client(monkeypatch)

    db.verwijder_gebruiker("tenant-A", "user-1")

    eq_paren = [(c.args[0], c.args[1]) for c in chain.eq.call_args_list]
    assert ("id", "user-1") in eq_paren
    assert ("tenant_id", "tenant-A") in eq_paren


@pytest.mark.unit
def test_verwijder_gebruiker_schrijft_naar_tenant_users_tabel(monkeypatch):
    """Tabelkeuze moet tenant_users zijn."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    db.verwijder_gebruiker("tenant-A", "user-1")

    client = tenant_factory.return_value
    client.table.assert_called_with("tenant_users")


@pytest.mark.unit
def test_verwijder_gebruiker_geeft_false_bij_nul_rijen(monkeypatch):
    """Cross-tenant DELETE \u2192 RLS blokkeert \u2192 resp.data == [] \u2192 (False, fout)."""
    import db
    _mock_tenant_client(monkeypatch, data_terug=[])

    ok, fout = db.verwijder_gebruiker("tenant-A", "user-van-b")

    assert ok is False
    laag = fout.lower()
    assert "niet gevonden" in laag or "geen toegang" in laag


@pytest.mark.unit
@pytest.mark.parametrize("leeg_tenant", ["", None])
def test_verwijder_gebruiker_weigert_lege_tenant_id(monkeypatch, leeg_tenant):
    """Lege/None tenant_id MOET vroeg bouncen."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.verwijder_gebruiker(leeg_tenant, "user-1")

    assert ok is False
    assert "ongeldige tenant" in fout.lower()
    assert not tenant_factory.called


@pytest.mark.unit
def test_verwijder_gebruiker_geeft_tuple_terug(monkeypatch):
    """Return is tuple[bool, str]."""
    import db
    _mock_tenant_client(monkeypatch)

    resultaat = db.verwijder_gebruiker("tenant-A", "user-1")

    assert isinstance(resultaat, tuple)
    assert len(resultaat) == 2
    assert isinstance(resultaat[0], bool)
    assert isinstance(resultaat[1], str)


@pytest.mark.unit
def test_verwijder_gebruiker_weigert_lege_user_id(monkeypatch):
    """Empty-guard op user_id \u2014 voorkomt DELETE zonder id-filter."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    ok, fout = db.verwijder_gebruiker("tenant-A", "")

    assert ok is False
    assert "gebruiker" in fout.lower() or "ongeldig" in fout.lower()
    assert not tenant_factory.called


# \u2500\u2500\u2500 laad_tenant_gebruikers (NIEUW) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
def test_laad_tenant_gebruikers_bestaat():
    """Nieuwe helper moet bestaan in db.py."""
    import db
    assert hasattr(db, "laad_tenant_gebruikers"), \
        "laad_tenant_gebruikers moet bestaan als tenant-scoped variant van laad_alle_gebruikers"


@pytest.mark.unit
def test_laad_tenant_gebruikers_heeft_tenant_id_als_eerste_param():
    """Contract: tenant_id als enige verplichte parameter."""
    import db
    params = list(inspect.signature(db.laad_tenant_gebruikers).parameters)
    assert params[0] == "tenant_id"


@pytest.mark.unit
def test_laad_tenant_gebruikers_gebruikt_tenant_client(monkeypatch):
    """MOET via get_tenant_client(tenant_id) lopen, niet via get_client()."""
    import db
    tenant_factory, oud_factory, admin_factory, _ = _mock_tenant_client(
        monkeypatch,
        data_terug=[{
            "id": "u1", "username": "x", "role": "user",
            "full_name": "X", "is_active": True, "tenant_id": "tenant-A",
            "email": "x@y.nl", "permissions": {},
        }],
    )

    db.laad_tenant_gebruikers("tenant-A")

    tenant_factory.assert_called_with("tenant-A")
    for factory in (oud_factory, admin_factory):
        if factory.called:
            client = factory.return_value
            table_calls = [c.args for c in client.table.call_args_list]
            assert ("tenant_users",) not in table_calls


@pytest.mark.unit
def test_laad_tenant_gebruikers_geeft_lege_lijst_bij_lege_tenant(monkeypatch):
    """Lege tenant_id \u2192 [] (geen exception, geen get_tenant_client call)."""
    import db
    tenant_factory, _, _, _ = _mock_tenant_client(monkeypatch)

    resultaat = db.laad_tenant_gebruikers("")

    assert resultaat == []
    assert not tenant_factory.called


@pytest.mark.unit
def test_laad_tenant_gebruikers_mapt_velden_naar_dict(monkeypatch):
    """Return-structuur MOET {id, username, role, full_name, is_active, tenant_id, email, permissions} bevatten."""
    import db
    _mock_tenant_client(
        monkeypatch,
        data_terug=[{
            "id": "u1", "username": "alice", "role": "manager",
            "full_name": "Alice Jones", "is_active": True, "tenant_id": "tenant-A",
            "email": "alice@x.nl", "permissions": {"mag_bestellen": True},
        }],
    )

    rijen = db.laad_tenant_gebruikers("tenant-A")

    assert len(rijen) == 1
    r = rijen[0]
    verwachte_keys = {
        "id", "username", "role", "full_name",
        "is_active", "tenant_id", "email", "permissions",
    }
    assert verwachte_keys.issubset(r.keys()), \
        f"Ontbrekende keys: {verwachte_keys - set(r.keys())}"
    assert r["username"] == "alice"
    assert r["permissions"] == {"mag_bestellen": True}


@pytest.mark.unit
def test_laad_tenant_gebruikers_email_none_wordt_lege_string(monkeypatch):
    """Als email NULL in DB \u2192 '' in return (defensief voor UI)."""
    import db
    _mock_tenant_client(
        monkeypatch,
        data_terug=[{
            "id": "u1", "username": "x", "role": "user",
            "full_name": "X", "is_active": True, "tenant_id": "tenant-A",
            "email": None, "permissions": {},
        }],
    )

    rijen = db.laad_tenant_gebruikers("tenant-A")

    assert rijen[0]["email"] == ""


# \u2500\u2500\u2500 laad_alle_gebruikers (blijft bestaan voor super_admin) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.mark.unit
def test_laad_alle_gebruikers_bestaat_nog():
    """`laad_alle_gebruikers()` MOET blijven \u2014 super_admin (page_admin) heeft dit nodig."""
    import db
    assert hasattr(db, "laad_alle_gebruikers"), \
        "laad_alle_gebruikers mag niet verwijderd worden \u2014 super_admin UI gebruikt dit"
