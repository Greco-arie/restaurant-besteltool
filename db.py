"""Supabase database client + authenticatie helpers."""
from __future__ import annotations
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    """Gecachte Supabase client — één instantie per Streamlit sessie."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


def laad_alle_tenants() -> list[dict]:
    """Geeft alle tenants terug als lijst van dicts."""
    try:
        resp = get_client().table("tenants").select("id, name, slug, status").order("name").execute()
        return resp.data or []
    except Exception:
        return []


def maak_tenant_aan(name: str, slug: str) -> str | None:
    """Maak een nieuwe tenant aan. Geeft UUID terug of None bij fout."""
    try:
        resp = get_client().table("tenants").insert({"name": name, "slug": slug}).execute()
        return resp.data[0]["id"] if resp.data else None
    except Exception:
        return None


def laad_alle_gebruikers() -> list[dict]:
    """Geeft alle gebruikers terug met tenantnaam."""
    try:
        resp = (
            get_client()
            .table("tenant_users")
            .select("id, username, role, full_name, is_active, tenant_id, tenants(name)")
            .order("username")
            .execute()
        )
        rows = []
        for u in (resp.data or []):
            rows.append({
                "id":           u["id"],
                "username":     u["username"],
                "role":         u["role"],
                "full_name":    u.get("full_name", ""),
                "is_active":    u.get("is_active", True),
                "tenant_id":    u["tenant_id"],
                "tenant_naam":  (u.get("tenants") or {}).get("name", "?"),
            })
        return rows
    except Exception:
        return []


def maak_gebruiker_aan(
    tenant_id: str,
    username:  str,
    password:  str,
    role:      str,
    full_name: str,
) -> bool:
    """Maak een nieuwe gebruiker aan. True als gelukt."""
    try:
        get_client().table("tenant_users").insert({
            "tenant_id": tenant_id,
            "username":  username,
            "password":  password,
            "role":      role,
            "full_name": full_name,
            "is_active": True,
        }).execute()
        return True
    except Exception:
        return False


def laad_leverancier_config(tenant_id: str) -> dict[str, dict]:
    """
    Geeft een dict terug: leverancier_naam → {email, aanhef}.
    Valt terug op lege waarden als de tabel nog niet bestaat of leeg is.
    """
    try:
        resp = (
            get_client()
            .table("leverancier_config")
            .select("leverancier, email, aanhef")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return {
            row["leverancier"]: {"email": row["email"], "aanhef": row["aanhef"]}
            for row in (resp.data or [])
        }
    except Exception:
        return {}


def sla_leverancier_config_op(
    tenant_id: str, leverancier: str, email: str, aanhef: str
) -> bool:
    """Sla e-mail en aanhef op voor een leverancier. True als gelukt."""
    try:
        get_client().table("leverancier_config").upsert({
            "tenant_id":   tenant_id,
            "leverancier": leverancier,
            "email":       email.strip(),
            "aanhef":      aanhef.strip(),
            "updated_at":  "now()",
        }, on_conflict="tenant_id,leverancier").execute()
        return True
    except Exception:
        return False


def verwijder_gebruiker(user_id: str) -> tuple[bool, str]:
    """Verwijder een gebruiker op basis van ID. Geeft (True, '') of (False, foutmelding)."""
    try:
        get_client().table("tenant_users").delete().eq("id", user_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def update_gebruiker(
    user_id:   str,
    username:  str,
    full_name: str,
    role:      str,
    password:  str | None = None,
) -> tuple[bool, str]:
    """Pas gebruikersgegevens aan. Geeft (True, '') of (False, foutmelding)."""
    try:
        data: dict = {
            "username":  username,
            "full_name": full_name,
            "role":      role,
        }
        if password:
            data["password"] = password
        get_client().table("tenant_users").update(data).eq("id", user_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def verwijder_tenant(tenant_id: str) -> tuple[bool, str]:
    """Verwijder een klant op basis van ID. Geeft (True, '') of (False, foutmelding)."""
    try:
        get_client().table("tenants").delete().eq("id", tenant_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def update_tenant(tenant_id: str, name: str) -> tuple[bool, str]:
    """Pas de naam van een klant aan. Geeft (True, '') of (False, foutmelding)."""
    try:
        get_client().table("tenants").update({"name": name}).eq("id", tenant_id).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def verificeer_gebruiker(username: str, password: str) -> dict | None:
    """
    Verifieer inloggegevens tegen de tenant_users tabel.
    Geeft dict terug met tenant_id, tenant_naam, username, role — of None als mislukt.
    """
    try:
        resp = (
            get_client()
            .table("tenant_users")
            .select("*, tenants(name)")
            .eq("username", username)
            .eq("password", password)
            .eq("is_active", True)
            .execute()
        )
        if resp.data:
            user = resp.data[0]
            tenant_info = user.get("tenants") or {}
            return {
                "tenant_id":   user["tenant_id"],
                "tenant_naam": tenant_info.get("name", "Onbekend"),
                "username":    user["username"],
                "role":        user["role"],
                "full_name":   user.get("full_name", user["username"]),
            }
    except Exception:
        pass
    return None
