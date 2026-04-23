"""Dag afsluiten — sluitstock, werkelijk resultaat, weerpreview, forecast trigger."""
from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
import streamlit as st
import forecast as fc
import recommendation as rc
import data_loader as dl
import learning
import weather as wt
import inventory as inv
import db
import email_service as mail
from cache import (
    get_products, get_sales_history, get_events, get_stock_count,
    get_reservations, get_leveranciers_dict, toon_voltooid_overlay,
)

PAGE_CLOSING  = "Dag afsluiten"
PAGE_FORECAST = "Forecast"
WEEKDAGEN     = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def _stuur_lage_voorraad_alert_indien_nodig(
    tenant_id: str,
    df_stock_nu: "pd.DataFrame",
    df_producten: "pd.DataFrame",
) -> None:
    """Stuurt een lage-voorraad alert naar de manager als er producten onder minimum zitten."""
    import pandas as pd
    try:
        stock_map = dict(zip(df_stock_nu["product_id"], df_stock_nu["hoeveelheid"].astype(float)))
        lage = []
        for _, prod in df_producten.iterrows():
            huidige = stock_map.get(str(prod["id"]), 0.0)
            if huidige < float(prod.get("minimumvoorraad", 0)):
                lage.append({
                    "naam":           prod["naam"],
                    "current_stock":  huidige,
                    "minimumvoorraad": float(prod.get("minimumvoorraad", 0)),
                    "eenheid":        prod.get("eenheid", ""),
                })
        if not lage:
            return

        # Zoek manager-email in tenant_users
        try:
            resp = (
                db.get_client()
                .table("tenant_users")
                .select("email")
                .eq("tenant_id", tenant_id)
                .in_("role", ["manager", "admin"])
                .eq("is_active", True)
                .execute()
            )
            emails = [r["email"] for r in (resp.data or []) if r.get("email")]
        except Exception:
            emails = []

        if not emails:
            return

        tenant_naam = st.session_state.get("tenant_naam", "Restaurant")
        for adres in emails:
            mail.verzend_lage_voorraad_alert(adres, tenant_naam, lage)
    except Exception:
        pass  # Alert-fout mag de sluiting niet blokkeren


def render() -> None:
    tenant_id = st.session_state.tenant_id
    user_naam = st.session_state.user_naam

    if st.session_state.forecast_result is not None:
        toon_voltooid_overlay("sluiting")

    st.title("Dag afsluiten")
    st.caption("Vul de dagcijfers in. Het systeem berekent forecast en besteladvies.")

    df_producten  = get_products(tenant_id)
    df_stock_base = get_stock_count(tenant_id)
    df_events_all = get_events()
    df_res_all    = get_reservations()

    datum_vandaag = date.today()
    datum_morgen  = datum_vandaag + timedelta(days=1)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Vandaag")
        datum_vandaag = st.date_input("Datum", value=datum_vandaag, format="DD/MM/YYYY")
        datum_morgen  = datum_vandaag + timedelta(days=1)
        covers = st.number_input(
            "Bonnen vandaag", min_value=0, step=1, value=None, placeholder="0",
            help="Totaal aantal orders/gasten vandaag",
        )
        omzet = st.number_input(
            "Omzet vandaag (€)", min_value=0.0, step=50.0, value=None, placeholder="0,00",
        )

    with col2:
        st.subheader("Morgen")
        st.info(
            f"Forecast voor: **{WEEKDAGEN[datum_morgen.weekday()].capitalize()} "
            f"{datum_morgen.strftime('%d %B %Y')}**"
        )

        morgen_str    = datum_morgen.isoformat()
        df_res_morgen = df_res_all[df_res_all["datum"] == morgen_str]
        default_rc    = int(df_res_morgen["reserved_covers"].sum()) if not df_res_morgen.empty else 0
        default_p25   = int(df_res_morgen["party_platters_25"].sum()) if not df_res_morgen.empty else 0
        default_p50   = int(df_res_morgen["party_platters_50"].sum()) if not df_res_morgen.empty else 0

        reserved_covers = st.number_input(
            "Reserveringen morgen (bonnen)", min_value=0, step=1,
            value=default_rc if default_rc > 0 else None, placeholder="0",
            help="Vaste vooruitbestellingen of groepen. Laat leeg als er niets is.",
        )

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            platters_25 = st.number_input(
                "Partycatering 25 st", min_value=0, step=1,
                value=default_p25 if default_p25 > 0 else None, placeholder="0",
            )
        with col_p2:
            platters_50 = st.number_input(
                "Partycatering 50 st", min_value=0, step=1,
                value=default_p50 if default_p50 > 0 else None, placeholder="0",
            )

        p25 = platters_25 or 0
        p50 = platters_50 or 0
        if p25 or p50:
            st.info(
                f"Party platters: {p25}× 25st + {p50}× 50st "
                f"(+{p25*25 + p50*50} extra minisnacks)"
            )

        bijzonderheden = st.text_area("Bijzonderheden", height=68, value="",
                                      placeholder="bv. lunch dicht, terras open, grote groep geannuleerd")

        ts_morgen = pd.Timestamp(datum_morgen)
        ev = df_events_all[df_events_all["datum"] == ts_morgen]
        if not ev.empty:
            row = ev.iloc[0]
            st.warning(
                f"Event morgen: **{row['event_name']}** — "
                f"covers ×{row['covers_multiplier']:.2f}, "
                f"friet ×{row['fries_ratio_multiplier']:.2f}, "
                f"desserts ×{row['desserts_ratio_multiplier']:.2f}"
            )

    st.divider()
    st.subheader("Sluitstock — kritieke artikelen")
    st.caption("Controleer en pas de voorraad aan. Dit wordt opgeslagen als live voorraad.")

    stock_map    = dict(zip(df_stock_base["product_id"], df_stock_base["hoeveelheid"]))
    stock_invoer = df_producten[["id", "naam", "leverancier", "eenheid"]].copy()
    stock_invoer["voorraad"] = stock_invoer["id"].map(stock_map).fillna(0.0)

    edited_stock = st.data_editor(
        stock_invoer,
        column_config={
            "id":          st.column_config.TextColumn("SKU",         disabled=True, width="small"),
            "naam":        st.column_config.TextColumn("Artikel",     disabled=True, width="medium"),
            "leverancier": st.column_config.TextColumn("Leverancier", disabled=True, width="medium"),
            "eenheid":     st.column_config.TextColumn("Eenheid",     disabled=True, width="small"),
            "voorraad":    st.column_config.NumberColumn("Voorraad",  min_value=0.0, step=1.0, width="small"),
        },
        hide_index=True,
        use_container_width=True,
        key="stock_editor",
    )

    gisteren = datum_vandaag - timedelta(days=1)
    if learning.heeft_open_werkelijk(tenant_id, gisteren):
        st.divider()
        st.subheader("Werkelijk resultaat van gisteren")
        st.caption(
            f"Voor **{WEEKDAGEN[gisteren.weekday()]} {gisteren.strftime('%d %B')}** "
            "is nog geen werkelijk resultaat ingevuld. Dit helpt het systeem beter te voorspellen."
        )
        col_w1, col_w2, col_w3 = st.columns([2, 2, 1])
        with col_w1:
            werkelijk_covers = st.number_input(
                "Werkelijk aantal bonnen gisteren", min_value=0, step=1,
                value=None, placeholder="0", key="werkelijk_covers",
            )
        with col_w2:
            werkelijk_omzet = st.number_input(
                "Werkelijke omzet gisteren (€)", min_value=0.0, step=50.0,
                value=None, placeholder="0,00", key="werkelijk_omzet",
            )
        with col_w3:
            st.write("")
            st.write("")
            if st.button("Opslaan", key="btn_werkelijk"):
                if werkelijk_covers:
                    opgeslagen = learning.log_werkelijk(
                        tenant_id, gisteren, int(werkelijk_covers),
                        float(werkelijk_omzet or 0.0),
                    )
                    if opgeslagen:
                        st.success("Resultaat opgeslagen.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.warning("Geen forecast gevonden voor deze datum.")
                else:
                    st.error("Vul het werkelijke aantal bonnen in.")

    st.divider()
    st.subheader("Weer morgen")
    weer_preview = wt.get_weer_morgen(datum_morgen)
    if weer_preview["beschikbaar"]:
        icon = weer_preview["icon"]
        w_col1, w_col2, w_col3 = st.columns(3)
        w_col1.metric("Temperatuur",   f"{weer_preview['temp_max']:.0f}°C")
        w_col2.metric("Regenrisico",   f"{weer_preview['precip_prob']}%")
        w_col3.metric("Terras factor", f"×{weer_preview['terras_factor']:.2f}")
        if weer_preview["terras_factor"] > 1.0:
            st.success(f"{icon} {weer_preview['label']}")
        else:
            st.info(f"{icon} {weer_preview['label']}")
    else:
        st.warning("Weerdata niet beschikbaar — geen terras-correctie toegepast.")

    st.divider()
    if st.button("Bereken forecast en besteladvies", type="primary", use_container_width=True):
        if not covers:
            st.error("Vul het aantal bonnen van vandaag in.")
            return

        covers_int     = int(covers)
        omzet_float    = float(omzet or 0.0)
        reserved_int   = int(reserved_covers or 0)
        platters25_int = int(p25)
        platters50_int = int(p50)

        df_history = get_sales_history(tenant_id)
        result     = fc.bereken_forecast(
            covers_vandaag   = covers_int,
            omzet_vandaag    = omzet_float,
            reserved_covers  = reserved_int,
            bijzonderheden   = bijzonderheden,
            df_history       = df_history,
            df_events        = df_events_all,
            df_reservations  = df_res_all,
            datum_morgen     = datum_morgen,
            tenant_id        = tenant_id,
            manager_override = None,
        )

        df_stock_nu = edited_stock[["id", "voorraad"]].rename(
            columns={"id": "product_id", "voorraad": "hoeveelheid"}
        ).copy()

        leveranciers_data = get_leveranciers_dict(tenant_id)
        advies_df = rc.bereken_alle_adviezen(
            df_producten    = df_producten,
            forecast_covers = result.forecast_covers,
            df_stock        = df_stock_nu,
            event_naam      = result.event_naam,
            fries_mult      = result.fries_mult,
            desserts_mult   = result.desserts_mult,
            drinks_mult     = result.drinks_factor,
            platters_25     = platters25_int,
            platters_50     = platters50_int,
            leveranciers    = leveranciers_data,
            vandaag         = datum_vandaag,
        )

        dl.sla_dag_op(tenant_id, datum_vandaag, covers_int, omzet_float,
                      reserved_int, bijzonderheden)
        dl.sla_stock_op(tenant_id, datum_vandaag, df_stock_nu)
        inv.sla_sluitstock_op(tenant_id, df_stock_nu, datum_vandaag, created_by=user_naam)
        inv.log_theoretisch_verbruik(tenant_id, datum_vandaag, covers_int, df_producten)
        learning.log_forecast(tenant_id, datum_morgen, result.forecast_covers,
                               result.event_naam, bijzonderheden)

        # Lage-voorraad alert naar manager (A5.3)
        _stuur_lage_voorraad_alert_indien_nodig(tenant_id, df_stock_nu, df_producten)

        st.cache_data.clear()

        st.session_state.closing_data    = {"datum_vandaag": datum_vandaag, "covers": covers, "omzet": omzet}
        st.session_state.forecast_result = result.as_dict()
        st.session_state.advies_df       = advies_df
        st.session_state.approved_orders = None
        st.session_state.pagina          = PAGE_FORECAST
        st.rerun()
