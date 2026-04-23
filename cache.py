"""Gecachte data-ophaalfuncties — gedeeld door app.py en views/."""
from __future__ import annotations
import pandas as pd
import streamlit as st
import data_loader as dl
import db
import permissions as perm


@st.cache_data
def get_products(tenant_id: str) -> pd.DataFrame:
    rows = db.laad_producten(tenant_id)
    if not rows:
        return pd.DataFrame(columns=[
            "id", "naam", "eenheid", "verpakkingseenheid",
            "vraag_per_cover", "minimumvoorraad", "buffer_pct",
            "leverancier", "actief",
        ])
    return pd.DataFrame(rows)


@st.cache_data
def get_sales_history(tenant_id: str) -> pd.DataFrame:
    return dl.load_sales_history(tenant_id)


@st.cache_data
def get_events() -> pd.DataFrame:
    return dl.load_events()


@st.cache_data
def get_stock_count(tenant_id: str) -> pd.DataFrame:
    return dl.load_stock_count(tenant_id)


@st.cache_data
def get_leveranciers_dict(tenant_id: str) -> dict[str, dict]:
    return db.laad_leveranciers_dict(tenant_id)


@st.cache_data
def get_leveranciers_lijst(tenant_id: str) -> list[dict]:
    return db.laad_leveranciers(tenant_id)


@st.cache_data
def get_reservations() -> pd.DataFrame:
    return dl.load_reservations()


def heeft_recht(recht: str) -> bool:
    """True als de ingelogde gebruiker het opgegeven recht heeft."""
    rol   = st.session_state.get("user_rol", "user")
    perms = st.session_state.get("user_permissions", {})
    return perm.heeft_recht(recht, rol, perms)


PAGE_CLOSING = "Dag afsluiten"


def toon_voltooid_overlay(page_key: str) -> None:
    """Toont een reset-knop + semi-transparant overlay als de flow al voltooid is."""
    if st.button(
        "Opnieuw beginnen — reset alle stappen",
        type="secondary",
        use_container_width=True,
        key=f"reset_{page_key}",
    ):
        for k in ["closing_data", "forecast_result", "advies_df", "approved_orders"]:
            st.session_state[k] = None
        st.session_state.pagina = PAGE_CLOSING
        st.rerun()

    st.markdown("""
    <style>
    .stMainBlockContainer > div:not(:first-child) {
        position: relative; pointer-events: none; user-select: none;
    }
    .stMainBlockContainer > div:not(:first-child)::after {
        content: ""; position: fixed; inset: 0;
        background: rgba(0,0,0,0.45); z-index: 999; pointer-events: none;
    }
    [data-testid="stSidebar"] { pointer-events: auto !important; z-index: 1000; }
    </style>
    """, unsafe_allow_html=True)
