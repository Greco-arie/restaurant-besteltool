"""Supabase database client + authenticatie helpers."""
from __future__ import annotations
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta

import jwt as pyjwt
import streamlit as st
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from models import SupplierData, UserSession

log = logging.getLogger(__name__)

# Whitelist voor tenant-gebruiker-rollen. super_admin is bewust uitgesloten \u2014
# alleen via `maak_gebruiker_aan` in de super_admin UI (page_admin) mag die
# rol toegekend worden, niet via `update_gebruiker`.
GELDIGE_TENANT_ROLLEN: frozenset[str] = frozenset({"user", "manager", "admin"})


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@st.cache_resource
def get_client() -> Client:
    """
    Gecachte Supabase client met service_role key — bypassed RLS server-side.

    DEPRECATED voor nieuwe code: gebruik expliciet één van:
      - get_admin_client()         → cross-tenant super_admin operaties
      - get_tenant_client(tenant_id) → tenant-scoped reads/writes (RLS afgedwongen)

    Bestaande callers blijven werken (zelfde gedrag, zelfde cache); migratie
    gebeurt gefaseerd. Zie docs/rls-policies.md.
    """
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["service_key"]
    return create_client(url, key)


def get_admin_client() -> Client:
    """
    Supabase client met service_role key — BYPASSED RLS.

    GEBRUIK voor:
      - Super_admin UI: tenants beheren, gebruikers aanmaken/verwijderen
      - Password reset (tokens over tenants heen)
      - Audit log INSERT (audit.log_audit_event schrijft altijd via service_role)
      - Cross-tenant rapportages (alleen voor super_admin-rol)
      - Migratiescripts / eenmalige data-opschoning

    GEBRUIK NIET voor:
      - Tenant-scoped reads/writes op: suppliers, products, sent_emails,
        sales_history, stock_count, forecast_log, current_inventory,
        inventory_adjustments, daily_usage, audit_log (SELECT)
      - Elke code die loopt onder een ingelogde manager/medewerker
      → In al deze gevallen: gebruik get_tenant_client(tenant_id).

    Rationale: service_role bypassed RLS volledig. Wie dit aanroept voor
    tenant-data negeert de v12-policies en riskeert cross-tenant data-leak.

    Zie docs/rls-policies.md voor het volledige beslisschema.
    """
    return get_client()


def get_tenant_client(tenant_id: str) -> Client:
    """
    Retourneert een Supabase client met een gesigned JWT voor de opgegeven tenant.
    JWT bevat role=authenticated + tenant_id, geldig 1 uur.
    RLS policies controleren tenant_id via auth.jwt() ->> 'tenant_id'.
    Niet gecached: elke aanroep genereert een verse JWT om expiry te voorkomen.
    """
    url        = st.secrets["supabase"]["url"]
    anon_key   = st.secrets["supabase"]["anon_key"]
    jwt_secret = st.secrets["supabase"]["jwt_secret"]
    now        = datetime.now(timezone.utc)
    payload    = {
        "iss":       "supabase",
        "role":      "authenticated",
        "iat":       int(now.timestamp()),
        "exp":       int((now + timedelta(hours=1)).timestamp()),
        "sub":       str(tenant_id),
        "tenant_id": str(tenant_id),
    }
    token = pyjwt.encode(payload, jwt_secret, algorithm="HS256")
    return create_client(
        url, anon_key,
        options=SyncClientOptions(headers={"Authorization": f"Bearer {token}"}),
    )


def laad_alle_tenants() -> list[dict]:
    """RLS-EXEMPT (super_admin): geeft alle tenants terug als lijst van dicts."""
    try:
        resp = get_client().table("tenants").select("id, name, slug, status").order("name").execute()
        return resp.data or []
    except Exception:
        return []


def maak_tenant_aan(name: str, slug: str) -> str | None:
    """RLS-EXEMPT (super_admin): maak nieuwe tenant aan. UUID terug of None bij fout."""
    try:
        resp = get_client().table("tenants").insert({"name": name, "slug": slug}).execute()
        return resp.data[0]["id"] if resp.data else None
    except Exception:
        return None


def _map_gebruiker_rij(u: dict, *, include_tenant_naam: bool = False) -> dict:
    """
    Map een `tenant_users` ruwe Supabase-rij naar het dict-formaat dat de UI verwacht.

    Single source of truth voor de veld-structuur \u2014 voorkomt drift tussen
    laad_alle_gebruikers (super_admin, include_tenant_naam=True) en
    laad_tenant_gebruikers (tenant-admin, zonder tenants-join).
    """
    rij = {
        "id":          u["id"],
        "username":    u["username"],
        "role":        u["role"],
        "full_name":   u.get("full_name", ""),
        "is_active":   u.get("is_active", True),
        "tenant_id":   u["tenant_id"],
        "email":       u.get("email") or "",
        "permissions": u.get("permissions") or {},
    }
    if include_tenant_naam:
        rij["tenant_naam"] = (u.get("tenants") or {}).get("name", "?")
    return rij


def laad_alle_gebruikers() -> list[dict]:
    """
    Geeft ALLE gebruikers (cross-tenant) terug met tenantnaam \u2014 SUPER_ADMIN UI.

    RLS-EXEMPT: via get_client() (service_role). Uitsluitend voor page_admin.py
    waar de super_admin alle klanten beheert. Tenant-admins/managers MOETEN
    `laad_tenant_gebruikers(tenant_id)` gebruiken.
    """
    try:
        resp = (
            get_client()
            .table("tenant_users")
            .select("id, username, role, full_name, is_active, tenant_id, email, permissions, tenants(name)")
            .order("username")
            .execute()
        )
        return [_map_gebruiker_rij(u, include_tenant_naam=True) for u in (resp.data or [])]
    except Exception:
        log.exception("laad_alle_gebruikers mislukt")
        return []


def laad_tenant_gebruikers(tenant_id: str) -> list[dict]:
    """
    Geeft alle gebruikers voor \u00e9\u00e9n tenant terug \u2014 tenant-scoped via RLS.

    Gebruik deze helper in page_instellingen.py (tenant-admin UI). Cross-tenant
    leken zijn uitgesloten door get_tenant_client(tenant_id): de RLS-policy
    filtert op auth.jwt() ->> 'tenant_id'.

    Lege tenant_id \u2192 [] (geen exception, geen JWT-mint).
    """
    if not tenant_id:
        return []
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("tenant_users")
            .select("id, username, role, full_name, is_active, tenant_id, email, permissions")
            .order("username")
            .execute()
        )
        return [_map_gebruiker_rij(u) for u in (resp.data or [])]
    except Exception:
        log.exception("laad_tenant_gebruikers mislukt (tenant=%s)", tenant_id)
        return []


def maak_gebruiker_aan(
    tenant_id:   str,
    username:    str,
    password:    str,
    role:        str,
    full_name:   str,
    permissions: dict | None = None,
    email:       str | None = None,
) -> bool:
    """
    RLS-EXEMPT: maak nieuwe gebruiker met bcrypt-gehasht wachtwoord. True = gelukt.

    super_admin/onboarding-path = legitiem via get_client(). De tenant-admin caller
    in page_instellingen.py valt onder STAP 1b-4 (session_state hardening) — tot dan
    is role-guard UI-only (LOW backlog). hash_password RPC = pure utility, geen
    tabel-access.
    """
    try:
        hash_resp = get_client().rpc("hash_password", {"p_password": password}).execute()
        hashed = hash_resp.data
        row: dict = {
            "tenant_id":   tenant_id,
            "username":    username,
            "password":    hashed,
            "role":        role,
            "full_name":   full_name,
            "is_active":   True,
            "permissions": permissions or {},
        }
        if email:
            row["email"] = email.lower().strip()
        get_client().table("tenant_users").insert(row).execute()
        from audit import log_audit_event
        log_audit_event(tenant_id, username, "gebruiker_aangemaakt",
                        {"username": username, "role": role})
        return True
    except Exception:
        return False


def verwijder_gebruiker(tenant_id: str, user_id: str) -> tuple[bool, str]:
    """
    Verwijder een gebruiker binnen de eigen tenant. Geeft (True, '') of (False, foutmelding).

    Tenant-scoped via JWT (RLS afgedwongen) + defense-in-depth `.eq("tenant_id", ...)`
    zodat cross-tenant DELETE onmogelijk is, ook als RLS per ongeluk niet greep.
    """
    if not tenant_id:
        return False, "Ongeldige tenant."
    if not user_id:
        return False, "Ongeldige gebruiker."
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("tenant_users")
            .delete()
            .eq("id", user_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not resp.data:
            return False, "Gebruiker niet gevonden of geen toegang."
        return True, ""
    except Exception as e:
        return False, str(e)


def update_gebruiker(
    tenant_id: str,
    user_id:   str,
    username:  str,
    full_name: str,
    role:      str,
    password:  str | None = None,
    email:     str | None = None,
) -> tuple[bool, str]:
    """
    Pas gebruikersgegevens aan binnen de eigen tenant. Geeft (True, '') of (False, foutmelding).

    Tenant-scoped via JWT (RLS afgedwongen) + defense-in-depth `.eq("tenant_id", ...)`.
    `role` moet in GELDIGE_TENANT_ROLLEN zitten \u2014 backend-whitelist voorkomt
    privilege-escalatie als de UI-laag gebypassed wordt (toekomstige REST-API,
    directe backend-aanroep in tests, etc.).

    hash_password RPC mag via get_client() omdat het een pure utility-RPC is
    (geen tabel-access, geen RLS-relevantie).
    """
    if not tenant_id:
        return False, "Ongeldige tenant."
    if not user_id:
        return False, "Ongeldige gebruiker."
    if role not in GELDIGE_TENANT_ROLLEN:
        return False, f"Ongeldige rol: {role!r}."
    try:
        data: dict = {
            "username":  username,
            "full_name": full_name,
            "role":      role,
        }
        if password:
            hash_resp = get_client().rpc("hash_password", {"p_password": password}).execute()
            data["password"] = hash_resp.data
        if email is not None:
            data["email"] = email.lower().strip() if email.strip() else None
        resp = (
            get_tenant_client(tenant_id)
            .table("tenant_users")
            .update(data)
            .eq("id", user_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not resp.data:
            return False, "Gebruiker niet gevonden of geen toegang."
        return True, ""
    except Exception as e:
        return False, str(e)


def verwijder_tenant(tenant_id: str) -> tuple[bool, str]:
    """RLS-EXEMPT (super_admin): verwijder klant op ID. Geeft (True, '') of (False, foutmelding)."""
    try:
        get_client().table("tenants").delete().eq("id", tenant_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def update_tenant(tenant_id: str, name: str) -> tuple[bool, str]:
    """RLS-EXEMPT (super_admin): pas klantnaam aan. Geeft (True, '') of (False, foutmelding)."""
    try:
        get_client().table("tenants").update({"name": name}).eq("id", tenant_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def verificeer_gebruiker(tenant_slug: str, username: str, password: str) -> dict | None:
    """
    Verifieer inloggegevens via pgcrypto crypt() — bcrypt-gehasht, tenant-scoped.
    Geeft dict terug met tenant_id, tenant_naam, username, role, permissions — of None als mislukt.

    RLS-EXEMPT (pre-auth login): JWT nog niet beschikbaar, verificeer_login RPC doet tenant-filter.
    """
    try:
        resp = get_client().rpc(
            "verificeer_login",
            {
                "p_tenant_slug": tenant_slug,
                "p_username":    username,
                "p_password":    password,
            },
        ).execute()
        if resp.data:
            user = resp.data[0]
            return {
                "tenant_id":   user["tenant_id"],
                "tenant_naam": user["tenant_naam"],
                "username":    user["username"],
                "role":        user["role"],
                "full_name":   user.get("full_name", user["username"]),
                "permissions": user.get("permissions") or {},
            }
    except Exception:
        pass
    return None


# ── Leveranciers ───────────────────────────────────────────────────────────

def laad_leveranciers(tenant_id: str) -> list[dict]:
    """Geeft alle actieve leveranciers voor de tenant als lijst."""
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("suppliers")
            .select("*")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def laad_leveranciers_dict(tenant_id: str) -> dict[str, dict]:
    """Geeft leveranciers als dict: naam → data, voor snelle lookup in berekeningen."""
    return {lev["name"]: lev for lev in laad_leveranciers(tenant_id)}


def maak_leverancier_aan(
    tenant_id:      str,
    name:           str,
    email:          str,
    aanhef:         str,
    lead_time_days: int,
    levert_ma: bool, levert_di: bool, levert_wo: bool, levert_do: bool,
    levert_vr: bool, levert_za: bool, levert_zo: bool,
) -> tuple[bool, str]:
    """Maak een nieuwe leverancier aan. Geeft (True, '') of (False, foutmelding)."""
    try:
        get_tenant_client(tenant_id).table("suppliers").insert({
            "tenant_id":      tenant_id,
            "name":           name.strip(),
            "email":          email.strip(),
            "aanhef":         aanhef.strip(),
            "lead_time_days": lead_time_days,
            "levert_ma": levert_ma, "levert_di": levert_di, "levert_wo": levert_wo,
            "levert_do": levert_do, "levert_vr": levert_vr, "levert_za": levert_za,
            "levert_zo": levert_zo,
            "is_active": True,
        }).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def update_leverancier(
    tenant_id:      str,
    supplier_id:    str,
    name:           str,
    email:          str,
    aanhef:         str,
    lead_time_days: int,
    levert_ma: bool, levert_di: bool, levert_wo: bool, levert_do: bool,
    levert_vr: bool, levert_za: bool, levert_zo: bool,
) -> tuple[bool, str]:
    """
    Pas een leverancier aan binnen de eigen tenant. Geeft (True, '') of (False, foutmelding).

    Tenant-scoped via JWT (RLS afgedwongen) + defense-in-depth `.eq("tenant_id", ...)`
    zodat cross-tenant mutatie onmogelijk is, ook als RLS per ongeluk niet greep.
    """
    if not tenant_id:
        return False, "Ongeldige tenant."
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("suppliers")
            .update({
                "name":           name.strip(),
                "email":          email.strip(),
                "aanhef":         aanhef.strip(),
                "lead_time_days": lead_time_days,
                "levert_ma": levert_ma, "levert_di": levert_di, "levert_wo": levert_wo,
                "levert_do": levert_do, "levert_vr": levert_vr, "levert_za": levert_za,
                "levert_zo": levert_zo,
            })
            .eq("id", supplier_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not resp.data:
            return False, "Leverancier niet gevonden of geen toegang."
        return True, ""
    except Exception as e:
        return False, str(e)


def verwijder_leverancier(tenant_id: str, supplier_id: str) -> tuple[bool, str]:
    """Soft delete leverancier (is_active=False), tenant-scoped via JWT + filter."""
    if not tenant_id:
        return False, "Ongeldige tenant."
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("suppliers")
            .update({"is_active": False})
            .eq("id", supplier_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not resp.data:
            return False, "Leverancier niet gevonden of geen toegang."
        return True, ""
    except Exception as e:
        return False, str(e)


# ── Gebruikersrechten ──────────────────────────────────────────────────────

def update_gebruiker_rechten(
    tenant_id: str,
    user_id:   str,
    rechten:   dict,
) -> tuple[bool, str]:
    """
    Sla granulaire rechten op voor een gebruiker binnen de eigen tenant.
    Geeft (True, '') of (False, foutmelding).

    Tenant-scoped via JWT (RLS afgedwongen) + defense-in-depth `.eq("tenant_id", ...)`
    zodat cross-tenant rechten-wijziging onmogelijk is, ook als RLS per ongeluk niet greep.
    """
    if not tenant_id:
        return False, "Ongeldige tenant."
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("tenant_users")
            .update({"permissions": rechten})
            .eq("id", user_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not resp.data:
            return False, "Gebruiker niet gevonden of geen toegang."
        return True, ""
    except Exception as e:
        return False, str(e)


# ── Verzendhistorie ────────────────────────────────────────────────────────

def sla_verzonden_email_op(
    tenant_id:     str,
    supplier_naam: str,
    bestel_datum:  str,
    resend_id:     str,
    supplier_id:   str | None = None,
) -> bool:
    """Sla een verzonden bestelling op in sent_emails. True als gelukt."""
    try:
        get_tenant_client(tenant_id).table("sent_emails").insert({
            "tenant_id":     tenant_id,
            "supplier_id":   supplier_id,
            "supplier_naam": supplier_naam,
            "bestel_datum":  bestel_datum,
            "resend_id":     resend_id,
            "status":        "sent",
        }).execute()
        return True
    except Exception:
        return False


def laad_verzonden_emails(tenant_id: str, limit: int = 50) -> list[dict]:
    """Geeft de laatste verzonden bestellingen terug voor een tenant."""
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("sent_emails")
            .select("supplier_naam, bestel_datum, resend_id, status, timestamp")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


# ── Producten ─────────────────────────────────────────────────────────────

_SUPPLIER_NAMEN: dict[str, str] = {
    "wholesale": "Hanos",
    "fresh":     "Vers Leverancier",
    "bakery":    "Bakkersland",
    "beer":      "Heineken Distrib.",
}


def laad_producten(tenant_id: str) -> list[dict]:
    """
    Geeft alle actieve producten voor de tenant als lijst van dicts.
    Kolommen matchen de legacy CSV-structuur: id (=sku_id), naam, eenheid,
    verpakkingseenheid, vraag_per_cover, minimumvoorraad, buffer_pct, leverancier, actief.
    """
    try:
        resp = (
            get_tenant_client(tenant_id)
            .table("products")
            .select("sku_id, naam, eenheid, verpakkingseenheid, vraag_per_cover, "
                    "minimumvoorraad, buffer_pct, is_actief, suppliers(name)")
            .eq("is_actief", True)
            .order("sku_id")
            .execute()
        )
        rows = []
        for p in (resp.data or []):
            supplier_naam = (p.get("suppliers") or {}).get("name", "Overig")
            rows.append({
                "id":                 p["sku_id"],
                "naam":               p["naam"],
                "eenheid":            p["eenheid"],
                "verpakkingseenheid": float(p["verpakkingseenheid"]),
                "vraag_per_cover":    float(p["vraag_per_cover"]),
                "minimumvoorraad":    float(p["minimumvoorraad"]),
                "buffer_pct":         float(p["buffer_pct"]),
                "leverancier":        supplier_naam,
                "actief":             p["is_actief"],
            })
        return rows
    except Exception:
        return []


def sla_product_op(
    tenant_id:          str,
    sku_id:             str,
    naam:               str,
    eenheid:            str,
    verpakkingseenheid: float,
    vraag_per_cover:    float,
    minimumvoorraad:    float,
    buffer_pct:         float,
    supplier_id:        str | None = None,
) -> tuple[bool, str]:
    """Upsert een product voor de tenant. Geeft (True, '') of (False, foutmelding)."""
    try:
        get_tenant_client(tenant_id).table("products").upsert({
            "tenant_id":          tenant_id,
            "sku_id":             sku_id,
            "naam":               naam,
            "eenheid":            eenheid,
            "verpakkingseenheid": verpakkingseenheid,
            "vraag_per_cover":    vraag_per_cover,
            "minimumvoorraad":    minimumvoorraad,
            "buffer_pct":         buffer_pct,
            "supplier_id":        supplier_id,
            "is_actief":          True,
        }, on_conflict="tenant_id,sku_id").execute()
        return True, ""
    except Exception as e:
        return False, str(e)


# ── Typed wrappers (Pydantic v2) — gebruik deze voor nieuwe code ──────────

def verificeer_gebruiker_typed(tenant_slug: str, username: str, password: str) -> UserSession | None:
    """Typed versie van verificeer_gebruiker — geeft UserSession of None."""
    raw = verificeer_gebruiker(tenant_slug, username, password)
    if raw is None:
        return None
    return UserSession.model_validate(raw)


def laad_leveranciers_typed(tenant_id: str) -> list[SupplierData]:
    """Typed versie van laad_leveranciers — geeft list[SupplierData]."""
    return [SupplierData.model_validate(row) for row in laad_leveranciers(tenant_id)]


def laad_leveranciers_dict_typed(tenant_id: str) -> dict[str, SupplierData]:
    """Typed versie van laad_leveranciers_dict — geeft dict[naam → SupplierData]."""
    return {s.name: s for s in laad_leveranciers_typed(tenant_id)}


# ── Password reset ─────────────────────────────────────────────────────────

def zoek_gebruiker_op_email(tenant_slug: str, email: str) -> dict | None:
    """RLS-EXEMPT (pre-auth reset-flow): zoek gebruiker op e-mail binnen tenant. Geeft dict of None."""
    try:
        tenant_resp = (
            get_client()
            .table("tenants")
            .select("id")
            .eq("slug", tenant_slug.strip())
            .execute()
        )
        if not tenant_resp.data:
            return None
        tenant_id = tenant_resp.data[0]["id"]
        user_resp = (
            get_client()
            .table("tenant_users")
            .select("id, username, tenant_id")
            .eq("tenant_id", tenant_id)
            .eq("email", email.lower().strip())
            .eq("is_active", True)
            .execute()
        )
        if user_resp.data:
            u = user_resp.data[0]
            return {"user_id": u["id"], "username": u["username"], "tenant_id": u["tenant_id"]}
    except Exception:
        pass
    return None


def maak_reset_token(tenant_id: str, user_id: str) -> str | None:
    """
    Genereer een veilig reset-token, sla de hash op in de database.
    Retourneert de plain token (alleen in e-mail sturen) of None bij fout.
    Invalideer eventuele openstaande tokens voor dezelfde gebruiker.

    RLS-EXEMPT (pre-auth reset-flow): token-mint vóór gebruiker is ingelogd.
    """
    try:
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        # Invalideer eventueel openstaande tokens voor deze gebruiker
        get_client().table("password_reset_tokens").update(
            {"used_at": now.isoformat()}
        ).eq("user_id", user_id).filter("used_at", "is", "null").execute()
        # Nieuw token aanmaken
        get_client().table("password_reset_tokens").insert({
            "tenant_id":  tenant_id,
            "user_id":    user_id,
            "token_hash": token_hash,
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        }).execute()
        return token
    except Exception:
        return None


def verifieer_reset_token(token: str) -> dict | None:
    """
    Verifieer of een reset-token geldig is (niet verlopen, niet gebruikt).
    Geeft {user_id, tenant_id} of None terug.

    RLS-EXEMPT (pre-auth reset-flow): token-verify vóór auth; tenant_id komt uit hash-match.
    """
    try:
        token_hash = _hash_token(token)
        now_iso = datetime.now(timezone.utc).isoformat()
        resp = (
            get_client()
            .table("password_reset_tokens")
            .select("user_id, tenant_id")
            .eq("token_hash", token_hash)
            .filter("used_at", "is", "null")
            .gt("expires_at", now_iso)
            .execute()
        )
        if resp.data:
            return {"user_id": resp.data[0]["user_id"], "tenant_id": resp.data[0]["tenant_id"]}
    except Exception:
        pass
    return None


def invalideer_token(token: str) -> bool:
    """RLS-EXEMPT (pre-auth reset-flow): markeer reset-token als gebruikt. True = gelukt."""
    try:
        get_client().table("password_reset_tokens").update(
            {"used_at": datetime.now(timezone.utc).isoformat()}
        ).eq("token_hash", _hash_token(token)).execute()
        return True
    except Exception:
        return False


def reset_wachtwoord(tenant_id: str, user_id: str, nieuw_wachtwoord: str) -> tuple[bool, str]:
    """
    Sla een nieuw gehashed wachtwoord op voor een gebruiker binnen de eigen tenant.
    Geeft (True, '') of (False, foutmelding).

    Tenant-scoped via JWT (RLS afgedwongen) + defense-in-depth `.eq("tenant_id", ...)`
    zodat cross-tenant wachtwoord-reset onmogelijk is, ook als RLS per ongeluk
    niet greep. `tenant_id` komt altijd uit `verifieer_reset_token` \u2014 die
    verifieert de token-hash v\u00f3\u00f3r hij de tenant_id teruggeeft, dus dit is een
    legitieme pre-auth tenant-context.

    hash_password RPC mag via get_client() (pure utility, geen tabel-access).
    """
    if not tenant_id:
        return False, "Ongeldige tenant."
    if not user_id:
        return False, "Ongeldige gebruiker."
    if not nieuw_wachtwoord:
        return False, "Wachtwoord mag niet leeg zijn."
    try:
        hash_resp = get_client().rpc("hash_password", {"p_password": nieuw_wachtwoord}).execute()
        resp = (
            get_tenant_client(tenant_id)
            .table("tenant_users")
            .update({"password": hash_resp.data})
            .eq("id", user_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not resp.data:
            return False, "Gebruiker niet gevonden of geen toegang."
        return True, ""
    except Exception as e:
        return False, str(e)


# ── Tenant onboarding ──────────────────────────────────────────────────────

def maak_tenant_met_admin(
    naam:           str,
    slug:           str,
    admin_username: str,
    admin_password: str,
    admin_email:    str,
) -> str | None:
    """
    Maak een tenant aan + een admin-gebruiker in één stap.
    Geeft tenant_id terug of None bij fout.

    RLS-EXEMPT (onboarding bootstrap): nieuwe tenant heeft nog geen context/JWT.
    """
    tenant_id = maak_tenant_aan(naam, slug)
    if not tenant_id:
        return None
    from audit import log_audit_event
    log_audit_event(tenant_id, admin_username, "tenant_aangemaakt",
                    {"naam": naam, "slug": slug})
    ok = maak_gebruiker_aan(
        tenant_id, admin_username, admin_password,
        "admin", admin_username, email=admin_email,
    )
    if not ok:
        # Tenant aangemaakt maar gebruiker mislukt — geef tenant_id terug zodat
        # de UI dit kan melden en de admin handmatig een gebruiker kan aanmaken.
        return tenant_id
    return tenant_id


# Audit logging: zie audit.py — importeer daar rechtstreeks vandaan.
