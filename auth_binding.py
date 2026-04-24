"""HMAC identity-binding helpers — STAP 1b-4 (Fase 3.1 RLS hardening).

Doel: cryptografisch bewijzen dat een tenant_id bij een ingelogde gebruiker
hoort, zonder DB-roundtrip en zonder te vertrouwen op muteerbare
session_state-velden.

Berekening:  HMAC-SHA256(jwt_secret, f"{tenant_id}|{username}")

Waarom HMAC-SHA256: deterministisch, snel, en zonder geheim niet te
vervalsen. Hergebruikt het bestaande jwt_secret dat de RLS-JWT's mint —
één geheim te roteren, niet meerdere.

Deze module is bewust geïsoleerd van db.py zodat db.py onder de 800-regel
grens blijft en om testen/reviewen eenvoudiger te houden.
"""
from __future__ import annotations

import hashlib
import hmac

import streamlit as st


def bereken_identity_proof(tenant_id: str, username: str, secret: str) -> str:
    """
    Bereken de identity-proof voor een (tenant_id, username)-paar.

    Args:
        tenant_id: UUID van de tenant.
        username:  Gebruikersnaam zoals door de RPC `verificeer_login` teruggegeven.
        secret:    jwt_secret uit st.secrets["supabase"]["jwt_secret"].

    Returns:
        Hexadecimale HMAC-SHA256 van `f"{tenant_id}|{username}"`.
    """
    return hmac.new(
        secret.encode(),
        f"{tenant_id}|{username}".encode(),
        hashlib.sha256,
    ).hexdigest()


def verifieer_binding_of_raise(tenant_id: str, jwt_secret: str) -> None:
    """
    Verifieer dat de HMAC-binding in session_state klopt voor `tenant_id`.

    - Ontbrekende `user_naam` of `identity_proof` → audit + RuntimeError.
    - Mismatch (gemanipuleerd tenant_id of proof) → audit + RuntimeError.
    - Match → returnt zonder effect; caller mag een JWT minten.

    Gebruikt `hmac.compare_digest` voor timing-safe vergelijking.
    """
    # Late import om circulaire imports te vermijden (audit → db → auth_binding).
    from audit import log_audit_event

    username     = st.session_state.get("user_naam") or ""
    stored_proof = st.session_state.get("identity_proof") or ""

    if not username or not stored_proof:
        log_audit_event(
            str(tenant_id),
            username or "onbekend",
            "identity_binding_ontbreekt",
            {"gevraagde_tenant_id": str(tenant_id)},
        )
        raise RuntimeError("Identity-binding ontbreekt — opnieuw inloggen vereist.")

    expected = bereken_identity_proof(str(tenant_id), username, jwt_secret)
    if not hmac.compare_digest(expected, stored_proof):
        log_audit_event(
            str(tenant_id),
            username,
            "identity_binding_mismatch",
            {"gevraagde_tenant_id": str(tenant_id)},
        )
        raise RuntimeError("Identity-binding mismatch — toegang geweigerd.")
