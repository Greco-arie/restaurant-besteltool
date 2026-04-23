"""Audit log helpers — centrale traceability van gebruikersacties.

Alle schrijf-acties gaan via service_role (bypast RLS) zodat een mislukte
audit-schrijf nooit de hoofdflow breekt. Lees-acties respecteren RLS via
get_tenant_client() in de app.
"""
from __future__ import annotations

from db import get_client


def log_audit_event(
    tenant_id: str,
    user_naam: str,
    actie:     str,
    details:   dict | None = None,
) -> None:
    """
    Log een audit-event naar audit_log (service_role — bypast RLS).
    Gooit nooit een exception naar de caller; fouten worden stil gelogd
    naar stdout zodat de hoofdflow nooit breekt op een audit-fout.
    """
    try:
        get_client().table("audit_log").insert({
            "tenant_id": tenant_id,
            "user_naam": user_naam,
            "actie":     actie,
            "details":   details or {},
        }).execute()
    except Exception as e:
        print(f"[audit_log] insert mislukt ({actie}): {e}")
