"""Sentry error tracking + structlog gestructureerde logging.

Dit module initialiseert beide systemen eenmalig bij import.
Gebruik de helpers log_event() en log_error() overal in de app.

Sentry tags worden automatisch verrijkt met tenant_id, user_id en pagina
via de Streamlit session_state (als die beschikbaar is op het moment van de exception).
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

# ── structlog configuratie ─────────────────────────────────────────────────
# JSON-output zodat logs leesbaar zijn door Streamlit Cloud / externe log-aggregators.

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)

_log = structlog.get_logger("besteltool")


# ── Sentry initialisatie ───────────────────────────────────────────────────

def _lees_sentry_dsn() -> str | None:
    try:
        import streamlit as st
        return st.secrets.get("sentry", {}).get("dsn") or os.getenv("SENTRY_DSN")
    except Exception:
        return os.getenv("SENTRY_DSN")


def _init_sentry() -> None:
    dsn = _lees_sentry_dsn()
    if not dsn:
        _log.warning("sentry_dsn_ontbreekt", hint="Stel SENTRY_DSN in via secrets of omgevingsvariabelen")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_logging = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR,
        )

        sentry_sdk.init(
            dsn=dsn,
            integrations=[sentry_logging],
            traces_sample_rate=0.1,       # 10% performance monitoring
            send_default_pii=False,        # geen persoonlijke data
            environment=os.getenv("ENVIRONMENT", "production"),
            release=os.getenv("GIT_SHA", "unknown"),
        )
        _log.info("sentry_geinitialiseerd", environment=os.getenv("ENVIRONMENT", "production"))
    except ImportError:
        _log.warning("sentry_niet_geinstalleerd", hint="pip install sentry-sdk")
    except Exception as e:
        _log.error("sentry_init_fout", fout=str(e))


# Initialiseer bij module-import (eenmalig door Python module cache)
_init_sentry()


# ── Sentry scope helpers ───────────────────────────────────────────────────

def _verrijk_sentry_scope() -> None:
    """Voeg tenant_id, user_id en pagina toe aan de actieve Sentry scope."""
    try:
        import sentry_sdk
        import streamlit as st

        with sentry_sdk.configure_scope() as scope:
            tenant_id = st.session_state.get("tenant_id")
            user_naam = st.session_state.get("user_naam")
            pagina    = st.session_state.get("pagina", "onbekend")

            if tenant_id:
                scope.set_tag("tenant_id", str(tenant_id))
            if user_naam:
                scope.set_user({"username": user_naam})
            scope.set_tag("pagina", str(pagina))
    except Exception:
        pass  # Sentry of Streamlit niet beschikbaar — stil falen


def stel_sentry_context_in(tenant_id: str, user_naam: str, pagina: str) -> None:
    """Roep aan bij elke paginawissel om de Sentry context up-to-date te houden."""
    try:
        import sentry_sdk
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("tenant_id", tenant_id)
            scope.set_tag("pagina", pagina)
            scope.set_user({"username": user_naam})
    except Exception:
        pass


# ── Publieke log-helpers ───────────────────────────────────────────────────

def log_event(event: str, **kwargs: Any) -> None:
    """Log een business-event als JSON (structlog). Geen exception = niet naar Sentry."""
    _verrijk_sentry_scope()
    _log.info(event, **kwargs)


def log_error(event: str, exc: BaseException | None = None, **kwargs: Any) -> None:
    """
    Log een fout als JSON én stuur naar Sentry.
    Als exc meegegeven is, wordt de volledige traceback doorgegeven.
    """
    _verrijk_sentry_scope()
    _log.error(event, **kwargs)

    try:
        import sentry_sdk
        if exc is not None:
            sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_message(event, level="error")
    except Exception:
        pass


def veroorzaak_test_exception() -> None:
    """Gooi opzettelijk een exception om Sentry-integratie te testen.
    Roep aan via de Streamlit UI of een unit-test.
    """
    _verrijk_sentry_scope()
    try:
        raise RuntimeError("Sentry test-exception — besteltool monitoring verificatie")
    except RuntimeError as exc:
        log_error("sentry_test_exception", exc=exc, bron="veroorzaak_test_exception")
        raise
