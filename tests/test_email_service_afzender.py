"""Tests voor _kies_afzender — per-tenant afzender via verified domains list.

Dekt RESEND_VERIFIED_DOMAINS (CSV) als nieuwe primaire schakelaar en
RESEND_DOMEIN_GEVERIFIEERD als backwards-compat fallback.
"""
from __future__ import annotations

import logging

import pytest

from email_service import _kies_afzender

SANDBOX = "onboarding@resend.dev"


@pytest.fixture(autouse=True)
def _schoon_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forceer een lege env voor elke test — voorkomt lekken via .env."""
    monkeypatch.delenv("RESEND_VERIFIED_DOMAINS", raising=False)
    monkeypatch.delenv("RESEND_DOMEIN_GEVERIFIEERD", raising=False)


def test_match_in_verified_domains_geeft_tenant_adres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESEND_VERIFIED_DOMAINS", "family-maarssen.besteltool.nl")

    afzender = _kies_afzender("family-maarssen")

    assert afzender == "no-reply@family-maarssen.besteltool.nl"


def test_multi_csv_waarde_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "RESEND_VERIFIED_DOMAINS",
        "alpha.besteltool.nl,beta.besteltool.nl,gamma.besteltool.nl",
    )

    afzender = _kies_afzender("beta")

    assert afzender == "no-reply@beta.besteltool.nl"


def test_whitespace_tolerant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "RESEND_VERIFIED_DOMAINS",
        "  alpha.besteltool.nl ,  beta.besteltool.nl  ",
    )

    afzender = _kies_afzender("beta")

    assert afzender == "no-reply@beta.besteltool.nl"


def test_case_insensitive_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEND_VERIFIED_DOMAINS", "FAMILY-MAARSSEN.BESTELTOOL.NL")

    afzender = _kies_afzender("family-maarssen")

    assert afzender == "no-reply@family-maarssen.besteltool.nl"


def test_legacy_flag_geeft_blanket_allow_met_deprecation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("RESEND_DOMEIN_GEVERIFIEERD", "true")
    caplog.set_level(logging.WARNING, logger="email_service")

    afzender = _kies_afzender("willekeurig-restaurant")

    assert afzender == "no-reply@willekeurig-restaurant.besteltool.nl"
    assert any("deprecated" in rec.getMessage().lower() for rec in caplog.records), (
        "verwacht deprecation-waarschuwing voor RESEND_DOMEIN_GEVERIFIEERD"
    )


def test_beide_unset_valt_terug_op_sandbox_met_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="email_service")

    afzender = _kies_afzender("any-tenant")

    assert afzender == SANDBOX
    assert any("sandbox" in rec.getMessage().lower() for rec in caplog.records), (
        "verwacht sandbox-warning"
    )


def test_custom_label_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEND_VERIFIED_DOMAINS", "family-maarssen.besteltool.nl")

    afzender = _kies_afzender("family-maarssen", label="alerts")

    assert afzender == "alerts@family-maarssen.besteltool.nl"


def test_slug_niet_in_verified_list_geeft_sandbox(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("RESEND_VERIFIED_DOMAINS", "alpha.besteltool.nl")
    caplog.set_level(logging.WARNING, logger="email_service")

    afzender = _kies_afzender("beta")

    assert afzender == SANDBOX
    assert any("sandbox" in rec.getMessage().lower() for rec in caplog.records)


def test_nieuwe_csv_wint_van_legacy_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Als CSV een match geeft, gebruik die — geen deprecation-pad."""
    monkeypatch.setenv("RESEND_VERIFIED_DOMAINS", "family-maarssen.besteltool.nl")
    monkeypatch.setenv("RESEND_DOMEIN_GEVERIFIEERD", "true")

    afzender = _kies_afzender("family-maarssen")

    assert afzender == "no-reply@family-maarssen.besteltool.nl"


# ── verzend_welkomstmail: afzender via _kies_afzender ──────────────────────

class _FakeEmails:
    """Vervangt resend.Emails — vangt de send() payload op zodat we 'from' kunnen asserten."""

    laatste_payload: dict | None = None

    @classmethod
    def send(cls, payload: dict) -> object:
        cls.laatste_payload = payload

        class _Resp:
            id = "fake-mail-id"
        return _Resp()


@pytest.fixture
def fake_resend(monkeypatch: pytest.MonkeyPatch):
    """Mock resend.Emails + RESEND_API_KEY zodat verzend_welkomstmail geen netwerk raakt."""
    import sys
    import types

    fake_resend_mod = types.ModuleType("resend")
    fake_resend_mod.Emails  = _FakeEmails
    fake_resend_mod.api_key = ""
    monkeypatch.setitem(sys.modules, "resend", fake_resend_mod)
    monkeypatch.setenv("RESEND_API_KEY", "fake-key")

    _FakeEmails.laatste_payload = None
    yield _FakeEmails


def test_welkomstmail_with_verified_domain_geeft_per_tenant_afzender(
    monkeypatch: pytest.MonkeyPatch, fake_resend
) -> None:
    monkeypatch.setenv("RESEND_VERIFIED_DOMAINS", "family-maarssen.besteltool.nl")
    from email_service import verzend_welkomstmail

    ok, _ = verzend_welkomstmail(
        to_email        = "manager@familymaarssen.nl",
        gebruikersnaam  = "sander",
        restaurant_naam = "Family Maarssen",
        tenant_slug     = "family-maarssen",
    )

    assert ok is True
    assert fake_resend.laatste_payload is not None
    assert fake_resend.laatste_payload["from"] == "welkom@family-maarssen.besteltool.nl"


def test_welkomstmail_zonder_verified_domain_valt_terug_op_sandbox(
    fake_resend,
) -> None:
    from email_service import verzend_welkomstmail

    ok, _ = verzend_welkomstmail(
        to_email        = "manager@familymaarssen.nl",
        gebruikersnaam  = "sander",
        restaurant_naam = "Family Maarssen",
        tenant_slug     = "family-maarssen",
    )

    assert ok is True
    assert fake_resend.laatste_payload["from"] == SANDBOX


def test_welkomstmail_legacy_flag_geeft_per_tenant_afzender(
    monkeypatch: pytest.MonkeyPatch, fake_resend
) -> None:
    """Backwards-compat: oude RESEND_DOMEIN_GEVERIFIEERD blijft werken."""
    monkeypatch.setenv("RESEND_DOMEIN_GEVERIFIEERD", "true")
    from email_service import verzend_welkomstmail

    ok, _ = verzend_welkomstmail(
        to_email        = "manager@familymaarssen.nl",
        gebruikersnaam  = "sander",
        restaurant_naam = "Family Maarssen",
        tenant_slug     = "family-maarssen",
    )

    assert ok is True
    assert fake_resend.laatste_payload["from"] == "welkom@family-maarssen.besteltool.nl"
