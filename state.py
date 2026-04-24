"""Typed accessors voor st.session_state — fundament voor views/ split."""
from __future__ import annotations
import time
from typing import Optional
import streamlit as st
from models import UserSession, ClosingData


# ── Gebruiker / sessie ─────────────────────────────────────────────────────

def get_user() -> Optional[UserSession]:
    """Geeft de ingelogde gebruiker terug, of None als niet ingelogd."""
    raw = st.session_state.get("user_session") or _legacy_user()
    if raw is None:
        return None
    if isinstance(raw, UserSession):
        return raw
    return UserSession.model_validate(raw)


def set_user(user: UserSession) -> None:
    st.session_state["user_session"] = user
    st.session_state["_login_timestamp"] = time.time()
    # legacy keys bijhouden voor backward compat met app.py
    st.session_state["ingelogd"]    = True
    st.session_state["tenant_id"]   = user.tenant_id
    st.session_state["tenant_naam"] = user.tenant_naam
    st.session_state["user_naam"]   = user.username
    st.session_state["user_rol"]    = user.role
    st.session_state["user_permissions"] = user.permissions
    # HMAC identity-binding — door get_tenant_client geverifieerd (STAP 1b-4).
    st.session_state["identity_proof"] = user.identity_proof


_CLOSING_FORM_KEYS = (
    "closing_datum_vandaag", "closing_covers", "closing_omzet",
    "closing_reserved_covers", "closing_platters_25", "closing_platters_50",
    "closing_bijzonderheden", "stock_editor",
    "werkelijk_covers", "werkelijk_omzet",
    "closing_data", "forecast_result", "advies_df", "approved_orders",
)


def clear_user() -> None:
    for key in ("user_session", "ingelogd", "tenant_id", "tenant_naam",
                "user_naam", "user_rol", "user_permissions", "identity_proof",
                *_CLOSING_FORM_KEYS):
        st.session_state.pop(key, None)


def require_user() -> UserSession:
    """Geeft de ingelogde gebruiker terug — stopt de app als niet ingelogd."""
    user = get_user()
    if user is None:
        st.error("Je bent niet ingelogd.")
        st.stop()
    return user


def _legacy_user() -> Optional[dict]:
    """Lees gebruiker uit legacy session_state keys (backward compat)."""
    if not st.session_state.get("ingelogd"):
        return None
    return {
        "tenant_id":      st.session_state.get("tenant_id", ""),
        "tenant_naam":    st.session_state.get("tenant_naam", ""),
        "username":       st.session_state.get("user_naam", ""),
        "role":           st.session_state.get("user_rol", "user"),
        "full_name":      st.session_state.get("user_naam", ""),
        "permissions":    st.session_state.get("user_permissions", {}),
        "identity_proof": st.session_state.get("identity_proof", ""),
    }


# ── Closing data ───────────────────────────────────────────────────────────

def get_closing_data() -> Optional[ClosingData]:
    raw = st.session_state.get("closing_data")
    if raw is None:
        return None
    if isinstance(raw, ClosingData):
        return raw
    return ClosingData.model_validate(raw)


def set_closing_data(data: ClosingData) -> None:
    st.session_state["closing_data"] = data.model_dump()


# ── Forecast result (dict opgeslagen voor backward compat) ────────────────

def get_forecast_result() -> Optional[dict]:
    return st.session_state.get("forecast_result")


def has_forecast() -> bool:
    return st.session_state.get("forecast_result") is not None


# ── Navigatie ─────────────────────────────────────────────────────────────

def get_pagina() -> str:
    return st.session_state.get("pagina", "")


def set_pagina(pagina: str) -> None:
    st.session_state["_prev_pagina"] = st.session_state.get("pagina")
    st.session_state["pagina"] = pagina
