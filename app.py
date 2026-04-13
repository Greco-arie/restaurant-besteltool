"""Restaurant Forecast & Besteladvies — multi-tenant versie."""
from __future__ import annotations
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import data_loader as dl
import forecast as fc
import recommendation as rc
import learning
import weather as wt
import inventory as inv
import db

st.set_page_config(
    page_title="Besteltool",
    page_icon="🍟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Pagina-namen ───────────────────────────────────────────────────────────
PAGE_CLOSING     = "Dag afsluiten"
PAGE_FORECAST    = "Forecast"
PAGE_REVIEW      = "Bestelreview"
PAGE_EXPORT      = "Export"
PAGE_INVENTARIS  = "Inventaris"
PAGE_PRODUCTEN   = "Producten & Leveranciers"
PAGE_LEERRAPPORT = "Leerrapport"
PAGE_ADMIN       = "Beheer"

WEEKDAGEN        = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
CONFIDENCE_LABEL = {"hoog": "Hoog", "gemiddeld": "Gemiddeld", "laag": "Laag"}

PAGINAS       = [PAGE_CLOSING, PAGE_FORECAST, PAGE_REVIEW, PAGE_EXPORT,
                 PAGE_INVENTARIS, PAGE_PRODUCTEN, PAGE_LEERRAPPORT]
PAGINAS_ADMIN = PAGINAS + [PAGE_ADMIN]


# ── Minimal design system ──────────────────────────────────────────────────
def _css() -> None:
    st.markdown("""
    <style>
    /* ── Design tokens ─────────────────────────────── */
    :root {
        --brand-primary:  #2E5AAC;
        --brand-hover:    #274F99;
        --brand-active:   #20427F;
        --soft-selection: #EAF1FF;
        --text:           #111827;
        --text-muted:     #4B5563;
        --page-bg:        #F9FAFB;
        --surface:        #FFFFFF;
        --surface-subtle: #F3F4F6;
        --border:         #CBD5E1;
        --success:        #16734A;
        --warning:        #B45309;
        --error:          #B42318;
        --accent-warm:    #A8643A;
        --focus-ring:     rgba(46,90,172,0.28);
        --disabled-bg:    #E5E7EB;
        --disabled-text:  #9CA3AF;
    }

    /* Achtergrond app */
    [data-testid="stApp"] { background-color: var(--page-bg); }

    /* Sidebar: subtle surface met subtiele rand */
    [data-testid="stSidebar"] {
        background-color: var(--surface-subtle) !important;
        border-right: 1px solid var(--border) !important;
    }

    /* Metric-kaarten: wit, lichte rand + schaduw */
    [data-testid="stMetric"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        padding: 1rem 1.25rem !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    }

    /* Primaire knop: Ink Indigo */
    button[kind="primary"] {
        background-color: var(--brand-primary) !important;
        border: none !important;
        border-radius: 10px !important;
    }
    button[kind="primary"]:hover {
        background-color: var(--brand-hover) !important;
    }
    button[kind="primary"]:active {
        background-color: var(--brand-active) !important;
    }
    button[kind="primary"]:focus {
        box-shadow: 0 0 0 3px var(--focus-ring) !important;
    }

    /* Formulier-container: wit met schaduw */
    [data-testid="stForm"] {
        background-color: var(--surface) !important;
        border: 1.5px solid var(--border) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.07) !important;
    }

    /* Invoervelden: zichtbare rand + Ink Indigo focus */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        border: 1.5px solid #C0C7D0 !important;
        border-radius: 6px !important;
        background-color: #FAFAFA !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--brand-primary) !important;
        background-color: var(--surface) !important;
        box-shadow: 0 0 0 3px var(--focus-ring) !important;
    }

    /* Expander: wit */
    [data-testid="stExpander"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }

    /* Tabs: actieve tab krijgt Ink Indigo indicator */
    .stTabs [data-baseweb="tab-list"] {
        background-color: var(--surface-subtle) !important;
        border-radius: 8px !important;
        padding: 3px !important;
        gap: 2px !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--surface) !important;
        border-radius: 6px !important;
        border-bottom: 2px solid var(--brand-primary) !important;
        color: var(--brand-primary) !important;
    }

    /* Divider iets zachter */
    hr { border-color: var(--border) !important; }

    /* Dataframe: subtiele rand + zebra-rows */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        background: var(--surface) !important;
    }
    tr:nth-child(even) td { background-color: var(--surface-subtle) !important; }
    tr[aria-selected="true"] td {
        background-color: var(--soft-selection) !important;
        color: var(--text) !important;
    }

    /* Link-knop (mailto): Ink Indigo */
    [data-testid="stLinkButton"] a {
        background-color: var(--brand-primary) !important;
        border-radius: 10px !important;
    }
    [data-testid="stLinkButton"] a:hover {
        background-color: var(--brand-hover) !important;
    }
    </style>
    """, unsafe_allow_html=True)


def _status_badge(label: str, kleur: str) -> str:
    """Geeft een gekleurde pill-badge terug als HTML-string.

    kleur: 'success' | 'warning' | 'error' | 'neutral'
    """
    colors: dict[str, tuple[str, str]] = {
        "success": ("#16734A", "#DCFCE7"),
        "warning": ("#B45309", "#FEF3C7"),
        "error":   ("#B42318", "#FEE2E2"),
        "neutral": ("#4B5563", "#F3F4F6"),
    }
    text_c, bg_c = colors.get(kleur, colors["neutral"])
    return (
        f'<span style="background:{bg_c};color:{text_c};'
        f'padding:2px 10px;border-radius:99px;font-size:0.78rem;font-weight:600;'
        f'display:inline-block;line-height:1.6">{label}</span>'
    )


# ── Gecachte data ──────────────────────────────────────────────────────────
@st.cache_data
def get_products() -> pd.DataFrame:
    return dl.load_products()

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
def get_leverancier_config(tenant_id: str) -> dict:
    return db.laad_leverancier_config(tenant_id)

@st.cache_data
def get_reservations() -> pd.DataFrame:
    return dl.load_reservations()


# ── Session state ──────────────────────────────────────────────────────────
def init_state() -> None:
    for key, val in {
        "ingelogd":        False,
        "tenant_id":       None,
        "tenant_naam":     None,
        "user_naam":       None,
        "user_rol":        None,
        "closing_data":    None,
        "forecast_result": None,
        "advies_df":       None,
        "approved_orders": None,
        "pagina":          PAGE_CLOSING,
        "_prev_pagina":    None,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Overlay voor voltooide stappen ────────────────────────────────────────
def _toon_voltooid_overlay(page_key: str) -> None:
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


# ── Inlogscherm ────────────────────────────────────────────────────────────
def page_login() -> None:
    col_l, col_m, col_r = st.columns([1, 1.4, 1])
    with col_m:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("Besteltool")
        st.caption("Voer je gegevens in om in te loggen.")
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            gebruiker  = st.text_input("Gebruikersnaam")
            wachtwoord = st.text_input("Wachtwoord", type="password")
            inloggen   = st.form_submit_button(
                "Inloggen", use_container_width=True, type="primary"
            )

        if inloggen:
            user = db.verificeer_gebruiker(gebruiker, wachtwoord)
            if user:
                st.session_state.ingelogd    = True
                st.session_state.tenant_id   = user["tenant_id"]
                st.session_state.tenant_naam = user["tenant_naam"]
                st.session_state.user_naam   = user["username"]
                st.session_state.user_rol    = user["role"]
                st.rerun()
            else:
                st.error("Gebruikersnaam of wachtwoord klopt niet.")


# ── Scherm 1 — Dag afsluiten ───────────────────────────────────────────────
def page_closing() -> None:
    tenant_id = st.session_state.tenant_id
    user_naam = st.session_state.user_naam

    if st.session_state.forecast_result is not None:
        _toon_voltooid_overlay("sluiting")

    st.title("Dag afsluiten")
    st.caption("Vul de dagcijfers in. Het systeem berekent forecast en besteladvies.")

    df_producten  = get_products()
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

    # ── Werkelijk resultaat van gisteren ──────────────────────────────────
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

    # ── Weerpreview ───────────────────────────────────────────────────────
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

        covers_int    = int(covers)
        omzet_float   = float(omzet or 0.0)
        reserved_int  = int(reserved_covers or 0)
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

        advies_df = rc.bereken_alle_adviezen(
            df_producten    = df_producten,
            forecast_covers = result["forecast_covers"],
            df_stock        = df_stock_nu,
            event_naam      = result["event_naam"],
            fries_mult      = result["fries_mult"],
            desserts_mult   = result["desserts_mult"],
            drinks_mult     = result["drinks_factor"],
            platters_25     = platters25_int,
            platters_50     = platters50_int,
        )

        dl.sla_dag_op(tenant_id, datum_vandaag, covers_int, omzet_float,
                      reserved_int, bijzonderheden)
        dl.sla_stock_op(tenant_id, datum_vandaag, df_stock_nu)
        inv.sla_sluitstock_op(tenant_id, df_stock_nu, datum_vandaag, created_by=user_naam)
        inv.log_theoretisch_verbruik(tenant_id, datum_vandaag, covers_int, df_producten)
        learning.log_forecast(tenant_id, datum_morgen, result["forecast_covers"],
                              result["event_naam"], bijzonderheden)

        st.cache_data.clear()

        st.session_state.closing_data    = {"datum_vandaag": datum_vandaag, "covers": covers, "omzet": omzet}
        st.session_state.forecast_result = result
        st.session_state.advies_df       = advies_df
        st.session_state.approved_orders = None
        st.session_state.pagina          = PAGE_FORECAST
        st.rerun()


# ── Scherm 2 — Forecast morgen ─────────────────────────────────────────────
def page_forecast() -> None:
    if st.session_state.approved_orders is not None:
        _toon_voltooid_overlay("forecast")

    st.title("Forecast morgen")

    if st.session_state.forecast_result is None:
        st.warning("Sluit eerst de dag af.")
        if st.button("Naar dag afsluiten"):
            st.session_state.pagina = PAGE_CLOSING
            st.rerun()
        return

    r          = st.session_state.forecast_result
    datum_str  = WEEKDAGEN[r["weekdag_morgen"]].capitalize() + r["datum_morgen"].strftime(" %d %B %Y")
    confidence = r["confidence"]

    st.subheader(f"Forecast voor {datum_str}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Verwachte bonnen",       r["forecast_covers"],
                delta=f"{r['forecast_covers'] - r['baseline']:+.0f} vs baseline")
    col2.metric("Verwachte omzet",        f"€ {r['forecast_omzet']:,.0f}")
    col3.metric("Betrouwbaarheid",        CONFIDENCE_LABEL[confidence])
    col4.metric("Baseline (zelfde dag)",  f"{r['baseline']:.0f}")

    if r["fries_mult"] > 1.0 or r["desserts_mult"] > 1.0:
        col_f, col_d = st.columns(2)
        if r["fries_mult"] > 1.0:
            col_f.metric("Friet multiplier",   f"×{r['fries_mult']:.2f}")
        if r["desserts_mult"] > 1.0:
            col_d.metric("Dessert multiplier", f"×{r['desserts_mult']:.2f}")

    if r["platters_25"] or r["platters_50"]:
        st.info(
            f"Partycatering: {r['platters_25']}× platter 25st + "
            f"{r['platters_50']}× platter 50st — extra minisnack-vraag verwerkt."
        )

    weer = r.get("weer", {})
    if weer.get("beschikbaar"):
        tf    = weer["terras_factor"]
        df_w  = weer["drinks_factor"]
        bericht = (
            f"{weer['icon']} **{weer['omschrijving']}** — "
            f"{weer['temp_max']:.0f}°C, {weer['precip_prob']}% regenrisico  \n"
            f"Terras-effect: covers ×{tf:.2f} | dranken ×{df_w:.2f}"
        )
        if tf > 1.0:
            st.success(bericht)
        else:
            st.info(bericht)

    st.divider()
    st.subheader("Berekening")
    for driver in r["drivers"]:
        st.write(f"• {driver}")

    if r["event_naam"] != "geen event":
        st.warning(f"Event actief: **{r['event_naam']}**")
    if confidence == "laag":
        st.error("Weinig historische data voor deze weekdag — extra aandacht bij review.")

    cf = r.get("correctie_factor", 1.0)
    if cf != 1.0:
        richting = "omhoog" if cf > 1.0 else "omlaag"
        st.info(
            f"Lerende correctie actief: forecast bijgesteld {richting} "
            f"(factor {cf:.3f}) op basis van eerdere dagresultaten."
        )

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Aanpassen", use_container_width=True):
            st.session_state.pagina = PAGE_CLOSING
            st.rerun()
    with col_b:
        if st.button("Naar bestelreview", type="primary", use_container_width=True):
            st.session_state.pagina = PAGE_REVIEW
            st.rerun()


# ── Scherm 3 — Bestelreview ────────────────────────────────────────────────
def page_review() -> None:
    if st.session_state.approved_orders is not None:
        _toon_voltooid_overlay("review")

    st.title("Bestelreview")

    if st.session_state.advies_df is None:
        st.warning("Bereken eerst de forecast.")
        if st.button("Naar dag afsluiten"):
            st.session_state.pagina = PAGE_CLOSING
            st.rerun()
        return

    r         = st.session_state.forecast_result
    advies_df = st.session_state.advies_df.copy()

    st.caption(f"Forecast: **{r['forecast_covers']} bonnen** — pas alleen uitzonderingen aan.")

    n_bestellen = int((advies_df["besteladvies"] > 0).sum())
    col1, col2, col3 = st.columns(3)
    col1.metric("Te bestellen",       n_bestellen)
    col2.metric("Voldoende in stock", len(advies_df) - n_bestellen)
    col3.metric("Leveranciers",
                advies_df[advies_df["besteladvies"] > 0]["leverancier"].nunique())

    st.divider()

    weergave = advies_df.rename(columns={
        "id":              "SKU",
        "naam":            "Artikel",
        "leverancier":     "Leverancier",
        "eenheid":         "Eenheid",
        "voorraad":        "Voorraad",
        "verwachte_vraag": "Verwachte vraag",
        "buffer_qty":      "Buffer",
        "platter_extra":   "Party extra",
        "besteladvies":    "Bestellen",
        "reden":           "Reden",
    })

    edited = st.data_editor(
        weergave.drop(columns=["SKU"]),
        column_config={
            "Artikel":         st.column_config.TextColumn(disabled=True, width="medium"),
            "Leverancier":     st.column_config.TextColumn(disabled=True, width="medium"),
            "Eenheid":         st.column_config.TextColumn(disabled=True, width="small"),
            "Voorraad":        st.column_config.NumberColumn(disabled=True, format="%.1f", width="small"),
            "Verwachte vraag": st.column_config.NumberColumn(disabled=True, format="%.1f", width="small"),
            "Buffer":          st.column_config.NumberColumn(disabled=True, format="%.1f", width="small"),
            "Party extra":     st.column_config.NumberColumn(disabled=True, format="%.0f", width="small"),
            "Bestellen":       st.column_config.NumberColumn(min_value=0.0, step=1.0, width="small"),
            "Reden":           st.column_config.TextColumn(disabled=True, width="large"),
        },
        hide_index=True,
        use_container_width=True,
        key="review_editor",
    )

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Terug naar forecast", use_container_width=True):
            st.session_state.pagina = PAGE_FORECAST
            st.rerun()
    with col_b:
        if st.button("Goedkeuren en exporteren", type="primary", use_container_width=True):
            approved = advies_df.copy()
            approved["besteladvies"] = edited["Bestellen"].values
            st.session_state.approved_orders = approved
            st.session_state.pagina = PAGE_EXPORT
            st.rerun()


# ── Scherm 4 — Export ─────────────────────────────────────────────────────
def page_export() -> None:
    tenant_id = st.session_state.tenant_id

    st.title("Export")
    st.caption("Bestellijst per leverancier")

    if st.session_state.approved_orders is None:
        st.warning("Keur eerst het besteladvies goed.")
        if st.button("Naar bestelreview"):
            st.session_state.pagina = PAGE_REVIEW
            st.rerun()
        return

    r            = st.session_state.forecast_result
    approved     = st.session_state.approved_orders
    lev_config   = get_leverancier_config(tenant_id)
    datum        = r["datum_morgen"].strftime("%Y-%m-%d")
    dag_naam     = WEEKDAGEN[r["weekdag_morgen"]].capitalize()

    st.caption(
        f"Bestelling voor **{dag_naam} {r['datum_morgen'].strftime('%d %B %Y')}** — "
        f"{r['forecast_covers']} bonnen verwacht"
    )

    per_lev = rc.groepeer_per_leverancier(approved)

    if not per_lev:
        st.success("Alles voldoende in stock — geen bestelling nodig.")
        return

    totaal = sum(len(df) for df in per_lev.values())
    col1, col2 = st.columns(2)
    col1.metric("Te bestellen artikelen", totaal)
    col2.metric("Leveranciers",           len(per_lev))

    st.divider()

    for lev, df_lev in per_lev.items():
        df_display = df_lev.rename(columns={
            "id":           "SKU",
            "naam":         "Artikel",
            "eenheid":      "Eenheid",
            "besteladvies": "Bestellen",
        })
        with st.expander(f"**{lev}** — {len(df_lev)} artikel(en)", expanded=True):
            st.dataframe(df_display, hide_index=True, use_container_width=True)

            cfg   = dl.SUPPLIER_CONFIG.get(lev, {})
            email = cfg.get("email", "")

            col_mail, col_csv = st.columns([3, 2])
            with col_mail:
                cfg_lev = lev_config.get(lev) or dl.SUPPLIER_CONFIG.get(lev, {})
                email   = cfg_lev.get("email", "")
                if not email:
                    st.warning(f"Geen e-mailadres voor {lev} — stel in via Beheer → Leveranciers")
                else:
                    mailto = dl.genereer_mailto(lev, df_lev, datum, config_override=cfg_lev)
                    components.html(
                        f"""<button
                          data-mailto="{mailto}"
                          onclick="(function(btn){{
                            var a = window.parent.document.createElement('a');
                            a.href = btn.getAttribute('data-mailto');
                            a.style.display = 'none';
                            window.parent.document.body.appendChild(a);
                            a.click();
                            setTimeout(function(){{ a.remove(); }}, 200);
                          }})(this);"
                          style="display:block;width:100%;padding:10px 16px;
                                 background:#111827;color:#ffffff;border:none;
                                 border-radius:6px;cursor:pointer;font-weight:500;
                                 font-size:14px;font-family:sans-serif;box-sizing:border-box;">
                          \U0001f4e7 Mail naar {lev} ({email})
                        </button>""",
                        height=52,
                        scrolling=False,
                    )
            with col_csv:
                csv = df_lev.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label     = f"Download {lev}.csv",
                    data      = csv,
                    file_name = f"bestelling_{datum}_{lev.replace(' ', '_')}.csv",
                    mime      = "text/csv",
                    key       = f"dl_{lev}",
                    use_container_width=True,
                )

    st.divider()
    alle_df = approved[approved["besteladvies"] > 0][
        ["leverancier", "id", "naam", "eenheid", "besteladvies"]
    ].copy()
    alle_df.columns = ["Leverancier", "SKU", "Artikel", "Eenheid", "Bestellen"]
    st.download_button(
        label     = "Download complete bestellijst",
        data      = alle_df.to_csv(index=False).encode("utf-8"),
        file_name = f"bestelling_{datum}_compleet.csv",
        mime      = "text/csv",
        use_container_width=True,
        type="primary",
    )

    if st.button("Nieuwe dag starten", use_container_width=True):
        for key in ["closing_data", "forecast_result", "advies_df", "approved_orders"]:
            st.session_state[key] = None
        st.session_state.pagina = PAGE_CLOSING
        st.rerun()


# ── Scherm 5 — Inventaris ─────────────────────────────────────────────────
def page_inventaris() -> None:
    tenant_id = st.session_state.tenant_id
    user_naam = st.session_state.user_naam

    st.title("Inventaris")
    st.caption(
        "Bekijk de huidige voorraad en corrigeer waar nodig. "
        "Elke correctie wordt opgeslagen en gebruikt om het systeem te verbeteren."
    )

    df_producten = get_products()
    df_inv       = inv.laad_huidige_voorraad(tenant_id)

    st.subheader("Huidige voorraad")

    if df_inv.empty:
        st.info("Nog geen voorraad geregistreerd. Sluit eerst een dag af.")
    else:
        sku_naam_map    = dict(zip(df_producten["id"], df_producten["naam"]))
        sku_eenheid_map = dict(zip(df_producten["id"], df_producten["eenheid"]))
        sku_lev_map     = dict(zip(df_producten["id"], df_producten["leverancier"]))
        min_stock_map   = dict(zip(df_producten["id"], df_producten["minimumvoorraad"].astype(float)))

        df_view = df_inv.copy()
        df_view["Artikel"]     = df_view["sku_id"].map(sku_naam_map).fillna(df_view["sku_id"])
        df_view["Eenheid"]     = df_view["sku_id"].map(sku_eenheid_map).fillna("")
        df_view["Leverancier"] = df_view["sku_id"].map(sku_lev_map).fillna("")
        df_view["Min."]        = df_view["sku_id"].map(min_stock_map).fillna(0)
        df_view["Status"]      = df_view.apply(
            lambda r: "Laag" if float(r["current_stock"]) < float(r["Min."]) else "OK", axis=1
        )
        df_view["Bijgewerkt"]  = pd.to_datetime(df_view["last_updated_at"]).dt.strftime("%d/%m %H:%M")

        st.dataframe(
            df_view[["Artikel", "Leverancier", "Eenheid", "current_stock", "Min.", "Status", "Bijgewerkt"]]
            .rename(columns={"current_stock": "Voorraad"}),
            hide_index=True,
            use_container_width=True,
        )

        laag = int((df_view["Status"] == "Laag").sum())
        if laag:
            st.warning(f"**{laag} artikel(en) onder minimumvoorraad** — controleer de bestelreview.")

    st.divider()
    st.subheader("Voorraad corrigeren")

    product_opties = dict(zip(df_producten["naam"], df_producten["id"]))

    with st.form("correctie_form"):
        col1, col2 = st.columns(2)
        with col1:
            gekozen_naam = st.selectbox("Artikel", options=list(product_opties.keys()))

        sku_id = product_opties[gekozen_naam]
        huidig = 0.0
        if not df_inv.empty:
            match  = df_inv[df_inv["sku_id"] == sku_id]
            huidig = float(match["current_stock"].iloc[0]) if not match.empty else 0.0

        with col2:
            nieuwe_stock = st.number_input(
                "Nieuwe voorraad", min_value=0.0, step=0.5, value=huidig
            )

        col3, col4 = st.columns(2)
        with col3:
            reden = st.selectbox("Reden", [
                "Telling gecorrigeerd",
                "Verspilling / afval",
                "Levering niet ingeboekt",
                "Personeelsmaaltijd / intern gebruik",
                "Portionering afwijking",
                "Overig",
            ])
        with col4:
            notitie = st.text_input("Notitie (optioneel)", value="")

        delta = nieuwe_stock - huidig
        st.caption(f"Huidig: **{huidig}** → Nieuw: **{nieuwe_stock}** (delta {delta:+.2f})")

        opslaan = st.form_submit_button("Correctie opslaan", type="primary", use_container_width=True)

    if opslaan:
        inv.sla_handmatige_correctie_op(
            tenant_id    = tenant_id,
            sku_id       = sku_id,
            nieuwe_stock = nieuwe_stock,
            reden        = reden,
            notitie      = notitie,
            created_by   = user_naam,
        )
        st.success(f"Voorraad voor **{gekozen_naam}** bijgewerkt naar {nieuwe_stock}.")
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Recente mutaties")

    df_correcties = inv.laad_recente_correcties(tenant_id)
    if df_correcties.empty:
        st.info("Nog geen mutaties geregistreerd.")
    else:
        df_correcties["Tijdstip"] = pd.to_datetime(
            df_correcties["created_at"]
        ).dt.strftime("%d/%m/%Y %H:%M")
        df_correcties["Artikel"] = df_correcties["sku_id"].map(
            dict(zip(df_producten["id"], df_producten["naam"]))
        ).fillna(df_correcties["sku_id"])

        st.dataframe(
            df_correcties[[
                "Tijdstip", "Artikel", "previous_stock", "new_stock",
                "quantity_delta", "adjustment_type", "reason", "note", "created_by"
            ]].rename(columns={
                "previous_stock":  "Was",
                "new_stock":       "Nieuw",
                "quantity_delta":  "Delta",
                "adjustment_type": "Type",
                "reason":          "Reden",
                "note":            "Notitie",
                "created_by":      "Door",
            }),
            hide_index=True,
            use_container_width=True,
        )

    st.divider()
    st.subheader("Verbruikspatronen")
    st.caption("Gebaseerd op historisch dagverbruik. Helpt bij het verbeteren van besteladvies.")

    df_analyse = inv.laad_verbruik_analyse(tenant_id)
    if df_analyse.empty:
        st.info("Nog geen verbruiksdata beschikbaar.")
    else:
        df_analyse["Artikel"] = df_analyse["sku_id"].map(
            dict(zip(df_producten["id"], df_producten["naam"]))
        ).fillna(df_analyse["sku_id"])
        st.dataframe(
            df_analyse[["Artikel", "datapunten", "gem_verbruik", "gem_per_cover"]].rename(columns={
                "datapunten":   "Dagen",
                "gem_verbruik": "Gem. dagverbruik",
                "gem_per_cover":"Gem. per bon",
            }).round(3),
            hide_index=True,
            use_container_width=True,
        )


# ── Scherm 6 — Producten & Leveranciers ──────────────────────────────────
def page_producten() -> None:
    tenant_id  = st.session_state.tenant_id
    lev_config = get_leverancier_config(tenant_id)

    st.title("Producten & Leveranciers")
    st.caption(
        "Volledig overzicht van alle artikelen per leverancier. "
        "E-mailadressen zijn instelbaar via Beheer → Leveranciers."
    )

    df = get_products()

    LEVERANCIERS_VOLGORDE = ["Hanos", "Vers Leverancier", "Bakkersland", "Heineken Distrib.", "Overig"]
    alle_leveranciers = [l for l in LEVERANCIERS_VOLGORDE if l in df["leverancier"].values]

    totaal_col1, totaal_col2, totaal_col3 = st.columns(3)
    totaal_col1.metric("Totaal artikelen",  len(df))
    totaal_col2.metric("Leveranciers",      df["leverancier"].nunique())
    totaal_col3.metric("Te bestellen SKUs", len(df[df["minimumvoorraad"] > 0]))

    st.divider()

    for lev in alle_leveranciers:
        df_lev  = df[df["leverancier"] == lev].copy()
        cfg     = lev_config.get(lev) or dl.SUPPLIER_CONFIG.get(lev, {})
        email   = cfg.get("email", "")
        n       = len(df_lev)

        email_badge = f" · {email}" if email else " · **geen e-mail ingesteld**"
        with st.expander(f"**{lev}** — {n} artikel(en){email_badge}", expanded=True):
            weergave = df_lev[[
                "id", "naam", "eenheid", "verpakkingseenheid",
                "vraag_per_cover", "buffer_pct", "minimumvoorraad",
            ]].rename(columns={
                "id":               "SKU",
                "naam":             "Artikel",
                "eenheid":          "Eenheid",
                "verpakkingseenheid": "Verpakking",
                "vraag_per_cover":  "Vraag/bon",
                "buffer_pct":       "Buffer %",
                "minimumvoorraad":  "Min. voorraad",
            }).copy()
            weergave["Buffer %"] = (weergave["Buffer %"] * 100).round(0).astype(int).astype(str) + "%"
            st.dataframe(weergave, hide_index=True, use_container_width=True)

            if not email:
                st.warning(
                    f"Geen e-mailadres ingesteld voor **{lev}**. "
                    "Stel dit in via Beheer → Leveranciers zodat bestellingen automatisch verstuurd kunnen worden."
                )


# ── Scherm 7 — Leerrapport ────────────────────────────────────────────────
def page_leerrapport() -> None:
    tenant_id = st.session_state.tenant_id

    st.title("Leerrapport")
    st.caption(
        "Elke dag dat het werkelijke resultaat wordt ingevuld, leert het systeem. "
        "De correctiefactor per weekdag wordt automatisch toegepast op de volgende forecast."
    )

    overzicht = learning.laad_accuracy_overzicht(tenant_id)

    if overzicht is None or overzicht.empty:
        st.info(
            "Nog geen data beschikbaar. Vul dagelijks het werkelijke resultaat in "
            "op het sluitscherm — na 3 dagen per weekdag start de automatische correctie."
        )
        _toon_log_tabel(tenant_id)
        return

    st.subheader("Accuraatheid per weekdag")
    st.dataframe(
        overzicht.style.format({
            "Gem. afwijking %": "{:+.1f}%",
            "Gem. abs. fout %": "{:.1f}%",
            "Correctiefactor":  "{:.3f}",
        }).background_gradient(subset=["Gem. abs. fout %"], cmap="RdYlGn_r"),
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "**Gem. afwijking %** = gemiddelde afwijking (+ = systeem zat te laag, - = te hoog). "
        "**Correctiefactor** = wordt automatisch toegepast op de volgende forecast voor die weekdag. "
        "Correctie is alleen actief na 3+ datapunten."
    )

    st.divider()
    st.subheader("Notities & patronen")
    st.caption(
        "Notities die op het sluitscherm worden geschreven, worden bijgehouden. "
        "Zodra dezelfde notitie 2+ keer is genoteerd, verschijnt hier de gemiddelde afwijking."
    )
    notitie_df = learning.laad_notitie_analyse(tenant_id)
    if notitie_df is not None:
        st.dataframe(
            notitie_df.style.format({"Gem. afwijking %": "{:+.1f}%"}),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info(
            "Nog geen patronen gevonden. Schrijf elke dag een korte notitie "
            "(bv. 'markt voor de deur', 'terras dicht regen'). "
            "Na 2 gelijke notities verschijnt hier de analyse."
        )

    st.divider()
    _toon_log_tabel(tenant_id)


def _toon_log_tabel(tenant_id: str) -> None:
    st.subheader("Forecast log")
    df = learning._alle_logs(tenant_id)
    if df.empty:
        st.info("Nog geen forecasts gelogd.")
        return

    WEEKDAGNAMEN = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
    df["weekdag_naam"] = df["weekdag"].map(
        lambda d: WEEKDAGNAMEN[int(d)] if pd.notna(d) else ""
    )
    df["datum"]     = pd.to_datetime(df["datum"]).dt.strftime("%d/%m/%Y")
    df["afwijking"] = (
        df["actual_covers"].astype(float) - df["predicted_covers"].astype(float)
    ).where(df["actual_covers"].notna())

    kolommen = ["datum", "weekdag_naam", "event_naam", "predicted_covers", "actual_covers", "afwijking"]
    if "notitie" in df.columns:
        kolommen.append("notitie")

    weergave = df[kolommen].rename(columns={
        "datum":            "Datum",
        "weekdag_naam":     "Dag",
        "event_naam":       "Event",
        "predicted_covers": "Voorspeld",
        "actual_covers":    "Werkelijk",
        "afwijking":        "Afwijking",
        "notitie":          "Notitie",
    })
    st.dataframe(weergave, hide_index=True, use_container_width=True)


# ── Admin ─────────────────────────────────────────────────────────────────
def page_admin() -> None:
    if st.session_state.user_rol != "admin":
        st.error("Geen toegang.")
        return

    tenant_id = st.session_state.tenant_id

    st.title("Beheer")
    st.caption("Klanten, gebruikers en leveranciersinstellingen beheren.")
    tab_klanten, tab_gebruikers, tab_leveranciers = st.tabs(["Klanten", "Gebruikers", "Leveranciers"])

    with tab_klanten:
        st.subheader("Bestaande klanten")
        tenants = db.laad_alle_tenants()
        if not tenants:
            st.info("Nog geen klanten gevonden.")
        for t in tenants:
            with st.expander(f"**{t['name']}** · {t['slug']} · {t['status']}"):
                with st.form(f"form_edit_tenant_{t['id']}"):
                    nieuwe_naam = st.text_input("Naam", value=t["name"])
                    if st.form_submit_button("Naam opslaan", type="primary"):
                        if not nieuwe_naam.strip():
                            st.error("Naam mag niet leeg zijn.")
                        else:
                            ok, fout = db.update_tenant(t["id"], nieuwe_naam.strip())
                            if ok:
                                st.success("Naam bijgewerkt.")
                                st.rerun()
                            else:
                                st.error(f"Opslaan mislukt: {fout}")

                st.divider()
                confirm_key = f"confirm_del_tenant_{t['id']}"
                if st.session_state.get(confirm_key):
                    st.warning(f"Weet je zeker dat je **{t['name']}** wilt verwijderen? Dit verwijdert ook alle gekoppelde data.")
                    col_ja, col_nee = st.columns(2)
                    with col_ja:
                        if st.button("Ja, verwijder", key=f"ja_tenant_{t['id']}", type="primary"):
                            ok, fout = db.verwijder_tenant(t["id"])
                            if ok:
                                st.session_state.pop(confirm_key, None)
                                st.success(f"{t['name']} verwijderd.")
                                st.rerun()
                            else:
                                st.error(f"Verwijderen mislukt: {fout}")
                    with col_nee:
                        if st.button("Annuleren", key=f"nee_tenant_{t['id']}"):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                else:
                    if st.button("Verwijder klant", key=f"del_tenant_{t['id']}"):
                        st.session_state[confirm_key] = True
                        st.rerun()

        st.divider()
        st.subheader("Nieuwe klant toevoegen")
        with st.form("form_nieuwe_tenant"):
            naam = st.text_input("Naam restaurant", placeholder="Restaurant De Bijenkorf")
            slug = st.text_input(
                "Slug (unieke code, kleine letters, geen spaties)",
                placeholder="de-bijenkorf",
                help="Gebruik alleen a-z, 0-9 en koppeltekens.",
            )
            if st.form_submit_button("Klant aanmaken"):
                if not naam or not slug:
                    st.error("Vul naam en slug in.")
                elif " " in slug:
                    st.error("Slug mag geen spaties bevatten.")
                else:
                    nieuw_id = db.maak_tenant_aan(naam.strip(), slug.strip().lower())
                    if nieuw_id:
                        st.success(f"Klant aangemaakt. UUID: `{nieuw_id}`")
                        st.info("Maak nu een gebruiker aan via de tab 'Gebruikers'.")
                    else:
                        st.error("Aanmaken mislukt — slug bestaat mogelijk al.")

    with tab_gebruikers:
        st.subheader("Bestaande gebruikers")
        gebruikers = db.laad_alle_gebruikers()
        ingelogd_username = st.session_state.get("user_naam", "")
        if not gebruikers:
            st.info("Nog geen gebruikers gevonden.")
        for g in gebruikers:
            label = f"**{g['username']}** · {g['tenant_naam']} · {g['role']}"
            with st.expander(label):
                with st.form(f"form_edit_user_{g['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nieuwe_username  = st.text_input("Gebruikersnaam", value=g["username"])
                        nieuwe_naam      = st.text_input("Volledige naam",  value=g.get("full_name", ""))
                    with col2:
                        nieuw_wachtwoord = st.text_input(
                            "Nieuw wachtwoord",
                            type="password",
                            placeholder="Laat leeg om niet te wijzigen",
                        )
                        nieuwe_rol = st.selectbox(
                            "Rol",
                            ["manager", "admin"],
                            index=0 if g["role"] == "manager" else 1,
                        )
                    if st.form_submit_button("Opslaan", type="primary"):
                        if not nieuwe_username.strip():
                            st.error("Gebruikersnaam mag niet leeg zijn.")
                        else:
                            ok, fout = db.update_gebruiker(
                                g["id"],
                                nieuwe_username.strip(),
                                nieuwe_naam.strip(),
                                nieuwe_rol,
                                nieuw_wachtwoord or None,
                            )
                            if ok:
                                st.success("Gegevens bijgewerkt.")
                                st.rerun()
                            else:
                                st.error(f"Opslaan mislukt: {fout}")

                st.divider()
                if g["username"] == ingelogd_username:
                    st.caption("Je kunt je eigen account niet verwijderen.")
                else:
                    confirm_key = f"confirm_del_user_{g['id']}"
                    if st.session_state.get(confirm_key):
                        st.warning(f"Weet je zeker dat je **{g['username']}** wilt verwijderen?")
                        col_ja, col_nee = st.columns(2)
                        with col_ja:
                            if st.button("Ja, verwijder", key=f"ja_user_{g['id']}", type="primary"):
                                ok, fout = db.verwijder_gebruiker(g["id"])
                                if ok:
                                    st.session_state.pop(confirm_key, None)
                                    st.success(f"Gebruiker {g['username']} verwijderd.")
                                    st.rerun()
                                else:
                                    st.error(f"Verwijderen mislukt: {fout}")
                        with col_nee:
                            if st.button("Annuleren", key=f"nee_user_{g['id']}"):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                    else:
                        if st.button("Verwijder gebruiker", key=f"del_user_{g['id']}"):
                            st.session_state[confirm_key] = True
                            st.rerun()

        st.divider()
        st.subheader("Nieuwe gebruiker toevoegen")
        tenants = db.laad_alle_tenants()
        if not tenants:
            st.warning("Maak eerst een klant aan.")
        else:
            tenant_opties = {t["name"]: t["id"] for t in tenants}
            with st.form("form_nieuwe_gebruiker"):
                gekozen_tenant = st.selectbox("Klant", options=list(tenant_opties.keys()))
                col1, col2 = st.columns(2)
                with col1:
                    gebruikersnaam = st.text_input("Gebruikersnaam")
                    volledige_naam = st.text_input("Volledige naam")
                with col2:
                    wachtwoord = st.text_input("Wachtwoord", type="password")
                    rol = st.selectbox("Rol", ["manager", "admin"])

                if st.form_submit_button("Gebruiker aanmaken"):
                    if not gebruikersnaam or not wachtwoord:
                        st.error("Vul gebruikersnaam en wachtwoord in.")
                    else:
                        tenant_id = tenant_opties[gekozen_tenant]
                        gelukt = db.maak_gebruiker_aan(
                            tenant_id, gebruikersnaam.strip(), wachtwoord,
                            rol, volledige_naam.strip()
                        )
                        if gelukt:
                            st.success(f"Gebruiker **{gebruikersnaam}** aangemaakt voor {gekozen_tenant}.")
                        else:
                            st.error("Aanmaken mislukt — gebruikersnaam bestaat mogelijk al.")

    with tab_leveranciers:
        st.subheader("E-mailadressen per leverancier")
        st.caption(
            "Stel het e-mailadres en de aanhef in per leverancier. "
            "De e-mailknop op de exportpagina gebruikt dit adres om automatisch "
            "een kant-en-klare bestelling te openen in jouw e-mailprogramma."
        )

        df_prod      = get_products()
        lev_config   = get_leverancier_config(tenant_id)
        leveranciers = sorted(df_prod["leverancier"].unique())

        for lev in leveranciers:
            cfg      = lev_config.get(lev) or dl.SUPPLIER_CONFIG.get(lev, {})
            huidig_email  = cfg.get("email", "")
            huidig_aanhef = cfg.get("aanhef", "Beste leverancier,")
            n_producten   = len(df_prod[df_prod["leverancier"] == lev])

            status = "Ingesteld" if huidig_email else "Geen e-mail"
            with st.expander(f"**{lev}** · {n_producten} artikelen · {status}", expanded=not huidig_email):
                with st.form(f"form_lev_{lev}"):
                    nieuw_email  = st.text_input(
                        "E-mailadres leverancier",
                        value=huidig_email,
                        placeholder="inkoop@leverancier.nl",
                        help="Bestellingen worden naar dit adres verzonden via je e-mailprogramma.",
                    )
                    nieuw_aanhef = st.text_input(
                        "Aanhef in e-mail",
                        value=huidig_aanhef,
                        placeholder="Beste leverancier,",
                    )
                    if st.form_submit_button("Opslaan", type="primary", use_container_width=True):
                        if not nieuw_email:
                            st.error("Vul een e-mailadres in.")
                        elif "@" not in nieuw_email:
                            st.error("Voer een geldig e-mailadres in.")
                        else:
                            ok = db.sla_leverancier_config_op(
                                tenant_id, lev, nieuw_email, nieuw_aanhef
                            )
                            if ok:
                                st.success(f"Opgeslagen: {lev} → {nieuw_email}")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("Opslaan mislukt — probeer opnieuw.")

        st.divider()
        st.caption(
            "**Hoe werkt de e-mailknop?**  \n"
            "Als je op de exportpagina klikt op 'Mail naar [leverancier]', opent jouw "
            "standaard e-mailprogramma (Outlook, Gmail, Apple Mail etc.) automatisch met "
            "het e-mailadres, onderwerp en de volledige bestellijst al ingevuld. "
            "Jij hoeft alleen nog op Verzenden te klikken."
        )


# ── Navigatie ──────────────────────────────────────────────────────────────
def main() -> None:
    _css()
    init_state()

    # Scroll naar boven bij paginawissel
    _prev = st.session_state.get("_prev_pagina")
    _curr = st.session_state.pagina
    if _prev != _curr:
        st.session_state._prev_pagina = _curr
        components.html(
            """<script>
            (function tryScroll(n) {
                var selectors = [
                    '[data-testid="stAppViewContainer"]',
                    '[data-testid="stMain"]',
                    'section.main',
                    '.main'
                ];
                selectors.forEach(function(sel) {
                    var el = window.parent.document.querySelector(sel);
                    if (el) { el.scrollTop = 0; }
                });
                if (n > 0) { setTimeout(function() { tryScroll(n - 1); }, 80); }
            })(6);
            </script>""",
            height=1,
            scrolling=False,
        )

    if not st.session_state.ingelogd:
        page_login()
        return

    with st.sidebar:
        st.markdown(
            f"**{st.session_state.tenant_naam}**  \n"
            f"{st.session_state.user_naam} · {st.session_state.user_rol}"
        )
        st.divider()

        nav_opties  = PAGINAS_ADMIN if st.session_state.user_rol == "admin" else PAGINAS
        _pagina_idx = nav_opties.index(st.session_state.pagina) if st.session_state.pagina in nav_opties else 0
        pagina = st.radio(
            "Navigatie",
            options=nav_opties,
            index=_pagina_idx,
            label_visibility="collapsed",
        )
        if pagina != st.session_state.pagina:
            st.session_state.pagina = pagina
            st.rerun()

        st.divider()
        st.caption("Voortgang")
        dag_ok  = st.session_state.closing_data is not None
        fc_ok   = st.session_state.forecast_result is not None
        best_ok = st.session_state.approved_orders is not None
        st.markdown(
            _status_badge("Dag afgesloten", "success") + "&nbsp; Dag afsluiten<br>"
            if dag_ok else
            _status_badge("Open", "warning") + "&nbsp; Dag afsluiten<br>",
            unsafe_allow_html=True,
        )
        st.markdown(
            _status_badge("Berekend", "success") + "&nbsp; Forecast<br>"
            if fc_ok else
            _status_badge("Open", "warning") + "&nbsp; Forecast<br>",
            unsafe_allow_html=True,
        )
        st.markdown(
            _status_badge("Goedgekeurd", "success") + "&nbsp; Bestelreview"
            if best_ok else
            _status_badge("Open", "warning") + "&nbsp; Bestelreview",
            unsafe_allow_html=True,
        )

        st.divider()
        if st.button("Uitloggen", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    scherm = st.session_state.pagina
    if scherm == PAGE_CLOSING:
        page_closing()
    elif scherm == PAGE_FORECAST:
        page_forecast()
    elif scherm == PAGE_REVIEW:
        page_review()
    elif scherm == PAGE_EXPORT:
        page_export()
    elif scherm == PAGE_INVENTARIS:
        page_inventaris()
    elif scherm == PAGE_PRODUCTEN:
        page_producten()
    elif scherm == PAGE_ADMIN:
        page_admin()
    else:
        page_leerrapport()


main()
