"""Unit tests voor auth_helpers.trigger_admin_password_reset (STAP 4d-bis).

De helper orchestreert: permission-check → email-check → basis_url-check →
db.maak_reset_token → email_service.verzend_reset_mail → audit.log_audit_event.

Alle Supabase- en mail-calls zijn gemockt; deze tests zijn pure unit-tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from models import UserSession


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def manager_met_recht() -> UserSession:
    return UserSession(
        tenant_id="tenant-A",
        tenant_naam="Family Maarssen",
        username="sander",
        role="manager",
        full_name="Sander de Manager",
        permissions={"gebruikers_beheren": True},
        identity_proof="a" * 64,
    )


@pytest.fixture
def manager_zonder_recht() -> UserSession:
    return UserSession(
        tenant_id="tenant-A",
        tenant_naam="Family Maarssen",
        username="sander",
        role="manager",
        full_name="Sander de Manager",
        permissions={"voorraad_tellen": True},
        identity_proof="a" * 64,
    )


@pytest.fixture
def super_admin_actor() -> UserSession:
    return UserSession(
        tenant_id="platform",
        tenant_naam="Platform",
        username="aris",
        role="super_admin",
        full_name="Aris",
        permissions={},
        identity_proof="b" * 64,
    )


@pytest.fixture
def target_user() -> dict:
    return {
        "id":         "user-42",
        "username":   "kok-bob",
        "tenant_id":  "tenant-A",
        "email":      "bob@familymaarssen.nl",
    }


@pytest.fixture
def target_user_andere_tenant() -> dict:
    return {
        "id":         "user-99",
        "username":   "kassa-eva",
        "tenant_id":  "tenant-B",
        "email":      "eva@andererestaurant.nl",
    }


@pytest.fixture
def mock_chain(monkeypatch):
    """Mock db.maak_reset_token, email_service.verzend_reset_mail, audit.log_audit_event.

    Default: token-mint slaagt, mail slaagt, audit slaagt.
    Tests passen mock-returnwaardes aan voor specifieke scenario's.
    """
    import auth_helpers  # noqa: F401 — wordt in fixture gepatcht

    fake_token = "tok_" + "x" * 32
    mocks = {
        "maak_reset_token":   MagicMock(return_value=fake_token),
        "verzend_reset_mail": MagicMock(return_value=(True, "queued")),
        "log_audit_event":    MagicMock(return_value=None),
    }
    monkeypatch.setattr("auth_helpers.maak_reset_token",   mocks["maak_reset_token"])
    monkeypatch.setattr("auth_helpers.verzend_reset_mail", mocks["verzend_reset_mail"])
    monkeypatch.setattr("auth_helpers.log_audit_event",    mocks["log_audit_event"])
    mocks["fake_token"] = fake_token
    return mocks


# ── Tests ───────────────────────────────────────────────────────────────────

def test_trigger_reset_zonder_email_geeft_false_en_meldt_geen_email(
    mock_chain, manager_met_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    target_zonder_email = {**target_user, "email": ""}
    ok, info = trigger_admin_password_reset(
        actor=manager_met_recht,
        target=target_zonder_email,
        basis_url="https://app.example.com",
    )

    assert ok is False
    assert info == "geen_email"
    mock_chain["maak_reset_token"].assert_not_called()
    mock_chain["verzend_reset_mail"].assert_not_called()
    mock_chain["log_audit_event"].assert_not_called()


def test_trigger_reset_succesvol_geeft_true_en_verstuurt_mail(
    mock_chain, manager_met_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    ok, info = trigger_admin_password_reset(
        actor=manager_met_recht,
        target=target_user,
        basis_url="https://app.example.com",
    )

    assert ok is True
    mock_chain["maak_reset_token"].assert_called_once_with("tenant-A", "user-42")
    mock_chain["verzend_reset_mail"].assert_called_once()
    kwargs = mock_chain["verzend_reset_mail"].call_args.kwargs
    assert kwargs["to_email"]       == "bob@familymaarssen.nl"
    assert kwargs["token"]          == mock_chain["fake_token"]
    assert kwargs["gebruikersnaam"] == "kok-bob"
    assert "https://app.example.com" in kwargs["reset_url"]
    assert mock_chain["fake_token"] in kwargs["reset_url"]


def test_trigger_reset_token_mint_faalt_geeft_false(
    mock_chain, manager_met_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    mock_chain["maak_reset_token"].return_value = None

    ok, info = trigger_admin_password_reset(
        actor=manager_met_recht,
        target=target_user,
        basis_url="https://app.example.com",
    )

    assert ok is False
    assert info == "token_mint_failed"
    mock_chain["verzend_reset_mail"].assert_not_called()


def test_trigger_reset_log_audit_event_met_juiste_velden(
    mock_chain, manager_met_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    trigger_admin_password_reset(
        actor=manager_met_recht,
        target=target_user,
        basis_url="https://app.example.com",
    )

    mock_chain["log_audit_event"].assert_called_once()
    args, kwargs = mock_chain["log_audit_event"].call_args
    # Signature: log_audit_event(tenant_id, user_naam, actie, details)
    assert args[2] == "admin_password_reset_triggered"
    details = args[3] if len(args) >= 4 else kwargs.get("details", {})
    assert details["actor_rol"]        == "manager"
    assert details["target_user_id"]   == "user-42"
    assert details["target_username"]  == "kok-bob"
    assert details["target_tenant_id"] == "tenant-A"
    assert details["cross_tenant"]     is False
    assert details["mail_sent"]        is True


def test_trigger_reset_cross_tenant_zet_cross_tenant_true_in_audit(
    mock_chain, super_admin_actor, target_user_andere_tenant
):
    from auth_helpers import trigger_admin_password_reset

    trigger_admin_password_reset(
        actor=super_admin_actor,
        target=target_user_andere_tenant,
        basis_url="https://app.example.com",
    )

    args, kwargs = mock_chain["log_audit_event"].call_args
    details = args[3] if len(args) >= 4 else kwargs.get("details", {})
    assert details["cross_tenant"]   is True
    assert details["actor_rol"]      == "super_admin"


def test_trigger_reset_audit_geschreven_naar_target_tenant_niet_actor_tenant(
    mock_chain, super_admin_actor, target_user_andere_tenant
):
    from auth_helpers import trigger_admin_password_reset

    trigger_admin_password_reset(
        actor=super_admin_actor,
        target=target_user_andere_tenant,
        basis_url="https://app.example.com",
    )

    args, _kwargs = mock_chain["log_audit_event"].call_args
    # Eerste positional arg is tenant_id van audit-rij — moet target zijn (forensics)
    assert args[0] == "tenant-B"
    assert args[0] != super_admin_actor.tenant_id


def test_trigger_reset_geeft_false_als_basis_url_leeg_is(
    mock_chain, manager_met_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    ok, info = trigger_admin_password_reset(
        actor=manager_met_recht,
        target=target_user,
        basis_url="",
    )

    assert ok is False
    assert info == "geen_basis_url"
    mock_chain["maak_reset_token"].assert_not_called()
    mock_chain["verzend_reset_mail"].assert_not_called()


def test_trigger_reset_mail_failure_logt_audit_alsnog_met_status_failed(
    mock_chain, manager_met_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    mock_chain["verzend_reset_mail"].return_value = (False, "smtp_error")

    ok, info = trigger_admin_password_reset(
        actor=manager_met_recht,
        target=target_user,
        basis_url="https://app.example.com",
    )

    assert ok is False
    assert info == "smtp_error"
    mock_chain["log_audit_event"].assert_called_once()
    args, kwargs = mock_chain["log_audit_event"].call_args
    details = args[3] if len(args) >= 4 else kwargs.get("details", {})
    assert details["mail_sent"] is False


def test_trigger_reset_audit_failure_breekt_niet_de_flow(
    mock_chain, manager_met_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    mock_chain["log_audit_event"].side_effect = RuntimeError("audit DB down")

    ok, info = trigger_admin_password_reset(
        actor=manager_met_recht,
        target=target_user,
        basis_url="https://app.example.com",
    )

    # Mail is wel verstuurd; audit-fout mag de flow niet breken
    assert ok is True
    mock_chain["verzend_reset_mail"].assert_called_once()


def test_trigger_reset_actor_zonder_recht_raised_permission_error(
    mock_chain, manager_zonder_recht, target_user
):
    from auth_helpers import trigger_admin_password_reset

    with pytest.raises(PermissionError):
        trigger_admin_password_reset(
            actor=manager_zonder_recht,
            target=target_user,
            basis_url="https://app.example.com",
        )

    mock_chain["maak_reset_token"].assert_not_called()
    mock_chain["verzend_reset_mail"].assert_not_called()
    mock_chain["log_audit_event"].assert_not_called()


def test_trigger_reset_manager_kan_geen_cross_tenant_target_resetten(
    mock_chain, manager_met_recht, target_user_andere_tenant
):
    """IDOR-guard: een manager/admin met recht 'gebruikers_beheren' mag
    alleen targets in z'n eigen tenant resetten. Cross-tenant is alleen
    voor super_admin. Defense-in-depth tegen st.session_state-tampering.
    """
    from auth_helpers import trigger_admin_password_reset

    with pytest.raises(PermissionError):
        trigger_admin_password_reset(
            actor=manager_met_recht,
            target=target_user_andere_tenant,
            basis_url="https://app.example.com",
        )

    mock_chain["maak_reset_token"].assert_not_called()
    mock_chain["verzend_reset_mail"].assert_not_called()
