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
