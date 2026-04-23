"""Manager dashboard — totaaloverzicht voor vandaag."""
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
import db
import inventory as inv
import permissions as perm


def _laad_omzet_vandaag(tenant_id: str) -> tuple[float | None, float | None]:
    """Geeft (omzet_vandaag, gemiddeld_zelfde_weekdag) terug."""
    try:
        resp = (
            db.get_client()
            .table("sales_history")
            .select("date, revenue_eur, covers")
            .eq("tenant_id", tenant_id)
            .order("date", desc=True)
            .limit(90)
            .execute()
        )
        if not resp.data:
            return None, None
        df = pd.DataFrame(resp.data)
        df["date"] = pd.to_datetime(df["date"])
        vandaag = date.today().isoformat()
        rij_vandaag = df[df["date"].dt.date == date.today()]
        omzet_vandaag = float(rij_vandaag["revenue_eur"].iloc[0]) if not rij_vandaag.empty else None

        weekdag = date.today().weekday()
        historisch = df[
            (df["date"].dt.weekday == weekdag) &
            (df["date"].dt.date != date.today())
        ]
        gem = float(historisch["revenue_eur"].mean()) if not historisch.empty else None
        return omzet_vandaag, gem
    except Exception:
        return None, None


def _laad_covers_vandaag(tenant_id: str) -> tuple[int | None, int | None]:
    """Geeft (covers_vandaag, forecast_morgen) terug."""
    try:
        resp = (
            db.get_client()
            .table("sales_history")
            .select("date, covers")
            .eq("tenant_id", tenant_id)
            .eq("date", date.today().isoformat())
            .execute()
        )
        covers_vandaag = int(resp.data[0]["covers"]) if resp.data else None

        fc_resp = (
            db.get_client()
            .table("forecast_log")
            .select("predicted_covers")
            .eq("tenant_id", tenant_id)
            .order("datum", desc=True)
            .limit(1)
            .execute()
        )
        forecast_morgen = int(fc_resp.data[0]["predicted_covers"]) if fc_resp.data else None
        return covers_vandaag, forecast_morgen
    except Exception:
        return None, None


def _laad_lage_voorraad(tenant_id: str) -> pd.DataFrame:
    """Geeft producten terug die onder hun minimumvoorraad zitten."""
    try:
        producten = db.laad_producten(tenant_id)
        if not producten:
            return pd.DataFrame()
        df_prod = pd.DataFrame(producten).rename(columns={"id": "sku_id"})
        df_stock = inv.laad_huidige_voorraad(tenant_id)
        if df_stock.empty:
            return pd.DataFrame()
        df = df_prod.merge(df_stock[["sku_id", "current_stock"]], on="sku_id", how="left")
        df["current_stock"] = df["current_stock"].fillna(0.0)
        return df[df["current_stock"] < df["minimumvoorraad"]][
            ["naam", "current_stock", "minimumvoorraad", "eenheid", "leverancier"]
        ].copy()
    except Exception:
        return pd.DataFrame()


def render() -> None:
    rol = st.session_state.get("user_rol", "user")
    if rol not in ("manager", "admin", "super_admin"):
        st.error("Geen toegang. Dit dashboard is alleen voor managers en admins.")
        return

    tenant_id = st.session_state.tenant_id

    st.title("Dashboard")
    st.caption(f"Overzicht voor vandaag — {date.today().strftime('%d %B %Y')}")

    # ── Rij 1: omzet + covers ─────────────────────────────────────────────
    omzet_vandaag, gem_omzet = _laad_omzet_vandaag(tenant_id)
    covers_vandaag, forecast_morgen = _laad_covers_vandaag(tenant_id)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if omzet_vandaag is not None:
            delta = omzet_vandaag - gem_omzet if gem_omzet else None
            st.metric(
                "Omzet vandaag",
                f"€ {omzet_vandaag:,.0f}",
                delta=f"€ {delta:+,.0f} vs gem." if delta is not None else None,
            )
        else:
            st.metric("Omzet vandaag", "—", help="Nog niet ingevuld vandaag")
    with col2:
        st.metric(
            "Gem. omzet (zelfde weekdag)",
            f"€ {gem_omzet:,.0f}" if gem_omzet else "—",
        )
    with col3:
        st.metric("Bonnen vandaag", covers_vandaag if covers_vandaag is not None else "—")
    with col4:
        st.metric(
            "Forecast morgen",
            forecast_morgen if forecast_morgen is not None else "—",
            help="Meest recente voorspelling"
        )

    st.divider()

    # ── Rij 2: lage voorraad + verzonden bestellingen ─────────────────────
    col_links, col_rechts = st.columns([1, 1])

    with col_links:
        st.subheader("Lage voorraad")
        df_laag = _laad_lage_voorraad(tenant_id)
        if df_laag.empty:
            st.success("Alle producten boven minimumvoorraad.")
        else:
            st.warning(f"{len(df_laag)} product(en) onder minimumvoorraad")
            st.dataframe(
                df_laag.rename(columns={
                    "naam": "Artikel",
                    "current_stock": "Voorraad",
                    "minimumvoorraad": "Minimum",
                    "eenheid": "Eenheid",
                    "leverancier": "Leverancier",
                }),
                hide_index=True,
                use_container_width=True,
            )

    with col_rechts:
        st.subheader("Laatste bestellingen")
        emails = db.laad_verzonden_emails(tenant_id, limit=5)
        if not emails:
            st.info("Nog geen bestellingen verzonden.")
        else:
            df_mail = pd.DataFrame(emails)
            df_mail = df_mail.rename(columns={
                "supplier_naam": "Leverancier",
                "bestel_datum":  "Leverdatum",
                "status":        "Status",
                "timestamp":     "Verzonden",
            })
            if "Verzonden" in df_mail.columns:
                df_mail["Verzonden"] = pd.to_datetime(df_mail["Verzonden"]).dt.strftime("%d/%m %H:%M")
            st.dataframe(
                df_mail[["Leverancier", "Leverdatum", "Status", "Verzonden"]],
                hide_index=True,
                use_container_width=True,
            )
