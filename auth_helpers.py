"""Admin orchestration helpers — geen directe Supabase-toegang.

Deze module orchestreert bestaande building-blocks (db, email_service, audit)
voor admin-workflows zoals het sturen van een wachtwoord-reset-link namens
een gebruiker. Pure orkestratie houdt db.py overzichtelijk (<800 regels) en
zorgt dat de audit/permission-laag op één centrale plek leeft.
"""
from __future__ import annotations

import logging
import os

import streamlit as st

from audit import log_audit_event
from db import maak_reset_token
from email_service import verzend_reset_mail
from models import UserSession
from permissions import heeft_recht

logger = logging.getLogger(__name__)


def lees_basis_url() -> str:
    """Lees app-basis-URL uit secrets of omgeving (zonder trailing slash).

    Hergebruik van het patroon in :mod:`views.page_password_reset` zodat
    admin-getriggerde reset-links exact dezelfde URL-structuur gebruiken.
    """
    try:
        url = st.secrets.get("app", {}).get("base_url", "")
    except Exception:
        url = ""
    if not url:
        url = os.getenv("APP_BASE_URL", "")
    return (url or "").rstrip("/")


def trigger_admin_password_reset(
    actor:     UserSession,
    target:    dict,
    basis_url: str,
) -> tuple[bool, str]:
    """Verstuur een wachtwoord-reset-link namens een admin/manager.

    Hergebruikt de zelfservice-flow: token-mint + mail. Schrijft een
    audit-rij naar de tenant van het target (forensics op de juiste plek).

    Parameters
    ----------
    actor     : ingelogde super_admin / admin / manager met recht
                "gebruikers_beheren".
    target    : dict-rij uit ``db.laad_tenant_gebruikers`` of
                ``db.laad_alle_gebruikers``. Verplichte sleutels:
                ``id``, ``username``, ``tenant_id``, ``email``.
    basis_url : applicatie-URL (zonder trailing slash) waaraan
                ``?token=…`` wordt toegevoegd voor de klikbare reset-link.

    Returns
    -------
    (ok, info)
        ``ok`` is True als de mail succesvol is verstuurd.
        ``info`` is een korte status-code voor UI-feedback:
        ``"geen_email"``, ``"geen_basis_url"``, ``"token_mint_failed"``,
        of de tweede tuple-waarde van :func:`verzend_reset_mail`.

    Raises
    ------
    PermissionError
        Als ``actor`` het recht ``"gebruikers_beheren"`` niet heeft.
        Defense-in-depth — UI behoort de knop ook al te verbergen.
    """
    if not heeft_recht("gebruikers_beheren", actor.role, actor.permissions):
        raise PermissionError(
            f"Actor {actor.username!r} (rol={actor.role}) mist recht "
            f"'gebruikers_beheren' voor admin-password-reset."
        )

    # IDOR-guard: alleen super_admin mag cross-tenant targets resetten.
    # Een admin/manager kan alleen z'n eigen tenant raken — defense-in-depth
    # tegen st.session_state-tampering.
    if actor.role != "super_admin" and target.get("tenant_id") != actor.tenant_id:
        raise PermissionError(
            f"Actor {actor.username!r} (tenant={actor.tenant_id}) mag geen "
            f"cross-tenant reset uitvoeren voor target tenant "
            f"{target.get('tenant_id')!r}."
        )

    target_email = (target.get("email") or "").strip()
    if not target_email:
        return False, "geen_email"

    if not (basis_url or "").strip():
        return False, "geen_basis_url"

    token = maak_reset_token(target["tenant_id"], target["id"])
    if not token:
        return False, "token_mint_failed"

    reset_url = f"{basis_url.rstrip('/')}?token={token}"
    ok, info = verzend_reset_mail(
        to_email        = target_email,
        token           = token,
        restaurant_naam = target["tenant_id"],
        gebruikersnaam  = target["username"],
        reset_url       = reset_url,
    )

    cross_tenant = actor.tenant_id != target["tenant_id"]
    details = {
        "actor_rol":        actor.role,
        "target_user_id":   target["id"],
        "target_username":  target["username"],
        "target_tenant_id": target["tenant_id"],
        "cross_tenant":     cross_tenant,
        "mail_sent":        bool(ok),
    }
    try:
        log_audit_event(
            target["tenant_id"],
            actor.username,
            "admin_password_reset_triggered",
            details,
        )
    except Exception as exc:
        # Audit is best-effort — primary flow gaat door, maar wél observable
        # zodat ops repeated failures kan zien.
        logger.warning("audit log_audit_event failed (best-effort): %s", exc)

    return bool(ok), info
