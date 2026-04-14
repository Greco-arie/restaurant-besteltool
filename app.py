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
PAGE_CLOSING      = "Dag afsluiten"
PAGE_FORECAST     = "Forecast"
PAGE_REVIEW       = "Bestelreview"
PAGE_EXPORT       = "Export"
PAGE_INVENTARIS   = "Inventaris"
PAGE_PRODUCTEN    = "Producten & Leveranciers"
PAGE_LEERRAPPORT  = "Leerrapport"
PAGE_INSTELLINGEN = "Instellingen"   # Voor manager en admin: leveranciers + gebruikers
PAGE_ADMIN        = "Beheer"         # Alleen admin: cross-tenant management

WEEKDAGEN        = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
CONFIDENCE_LABEL = {"hoog": "Hoog", "gemiddeld": "Gemiddeld", "laag": "Laag"}

# Pagina's per rol
_PAGINAS_BASIS  = [PAGE_CLOSING, PAGE_FORECAST, PAGE_REVIEW, PAGE_EXPORT,
                   PAGE_INVENTARIS, PAGE_PRODUCTEN, PAGE_LEERRAPPORT]
PAGINAS         = _PAGINAS_BASIS                                       # gebruiker (read-only)
PAGINAS_MANAGER = _PAGINAS_BASIS + [PAGE_INSTELLINGEN]                 # manager
PAGINAS_ADMIN   = _PAGINAS_BASIS + [PAGE_INSTELLINGEN, PAGE_ADMIN]     # admin


def _nav_paginas() -> list[str]:
    """Geeft de navigatielijst terug op basis van de rol van de ingelogde gebruiker."""
    rol = st.session_state.get("user_rol", "user")
    if rol == "admin":
        return PAGINAS_ADMIN
    if rol == "manager":
        return PAGINAS_MANAGER
    return PAGINAS


def _heeft_recht(recht: str) -> bool:
    """True als de ingelogde gebruiker het opgegeven recht heeft.

    Admin en manager hebben altijd alle rechten.
    Gebruiker (rol='user') heeft rechten op basis van zijn permissions dict.

    Beschikbare rechten:
      voorraad_wijzigen  — voorraad handmatig aanpassen
      orders_versturen   — bestellingen goedkeuren en versturen
      acties             — acties/campagnes aanmaken
      recepten_beheren   — recepten toevoegen en wijzigen
    """
    rol = st.session_state.get("user_rol", "user")
    if rol in ("admin", "manager"):
        return True
    perms = st.session_state.get("user_permissions", {})
    return bool(perms.get(recht, False))


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
def get_leveranciers_dict(tenant_id: str) -> dict[str, dict]:
    """Gecachte leveranciersdata voor gebruik in de bestelberekening."""
    return db.laad_leveranciers_dict(tenant_id)

@st.cache_data
def get_leveranciers_lijst(tenant_id: str) -> list[dict]:
    """Gecachte leverancierslijst voor gebruik in de UI."""
    return db.laad_leveranciers(tenant_id)

@st.cache_data
def get_reservations() -> pd.DataFrame:
    return dl.load_reservations()


# ── Session state ──────────────────────────────────────────────────────────
def init_state() -> None:
    for key, val in {
        "ingelogd":          False,
        "tenant_id":         None,
        "tenant_naam":       None,
        "user_naam":         None,
        "user_rol":          None,
        "user_permissions":  {},    # Granulaire rechten voor de 'user' rol
        "closing_data":      None,
        "forecast_result":   None,
        "advies_df":         None,
        "approved_orders":   None,
        "pagina":            PAGE_CLOSING,
        "_prev_pagina":      None,
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
                st.session_state.ingelogd           = True
                st.session_state.tenant_id          = user["tenant_id"]
                st.session_state.tenant_naam        = user["tenant_naam"]
                st.session_state.user_naam          = user["username"]
                st.session_state.user_rol           = user["role"]
                st.session_state.user_permissions   = user.get("permissions", {})
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

        leveranciers_data = get_leveranciers_dict(tenant_id)
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
            leveranciers    = leveranciers_data,
            vandaag         = datum_vandaag,
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

    # ── Leveringsschema ───────────────────────────────────────────────────
    tenant_id_fc = st.session_state.tenant_id
    leveranciers_data = get_leveranciers_dict(tenant_id_fc)
    if leveranciers_data:
        datum_vandaag_fc = r["datum_morgen"] - timedelta(days=1)
        st.divider()
        st.subheader("Volgende leveringen")
        lev_cols = st.columns(len(leveranciers_data))
        for idx, (lev_naam, lev_data) in enumerate(sorted(leveranciers_data.items())):
            info = rc.volgende_leverdag_info(lev_naam, datum_vandaag_fc, leveranciers_data)
            dag_nl   = info["weekdag_naam"].capitalize()
            datum_nl = info["datum"].strftime("%d %b")
            label    = f"**{lev_naam}**"
            waarde   = f"{dag_nl} {datum_nl}"
            delta    = f"over {info['dagen']} dag{'en' if info['dagen'] != 1 else ''}"
            with lev_cols[idx]:
                st.metric(label, waarde, delta=delta)
                if info["te_laat"]:
                    st.warning(
                        f"Bestel vandaag! Levertijd {info['lead_time_days']}d — "
                        f"anders te laat voor {dag_nl}.",
                        icon="⚠️",
                    )

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
        "id":                 "SKU",
        "naam":               "Artikel",
        "leverancier":        "Leverancier",
        "eenheid":            "Eenheid",
        "voorraad":           "Voorraad",
        "verwachte_vraag":    "Verwachte vraag",
        "buffer_qty":         "Buffer",
        "platter_extra":      "Party extra",
        "dagen_tot_levering": "Dagen",
        "besteladvies":       "Bestellen",
        "reden":              "Reden",
    })

    kan_goedkeuren = _heeft_recht("orders_versturen")
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
            "Dagen":           st.column_config.NumberColumn(disabled=True, format="%d d", width="small",
                                                             help="Aantal dagen tot eerstvolgende levering"),
            "Bestellen":       st.column_config.NumberColumn(
                                   min_value=0.0, step=1.0, width="small",
                                   disabled=not kan_goedkeuren,
                               ),
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
        if kan_goedkeuren:
            if st.button("Goedkeuren en exporteren", type="primary", use_container_width=True):
                approved = advies_df.copy()
                approved["besteladvies"] = edited["Bestellen"].values
                st.session_state.approved_orders = approved
                st.session_state.pagina = PAGE_EXPORT
                st.rerun()
        else:
            st.info("Je hebt geen recht om bestellingen goed te keuren. Vraag de manager.")


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

    if not _heeft_recht("voorraad_wijzigen"):
        st.info("Je hebt geen recht om de voorraad handmatig te wijzigen. Vraag de manager.")
        return

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


# ── Wizard: Nieuw product toevoegen ──────────────────────────────────────
def _wizard_reset() -> None:
    """Zet alle wizard-state terug naar begin."""
    for k in list(st.session_state.keys()):
        if k.startswith("wiz_"):
            del st.session_state[k]


def _wizard_nieuw_product(tenant_id: str, df_producten: pd.DataFrame) -> None:
    """
    Stapsgewijs ontvouwend formulier voor een nieuw product.

    Stap 1 — Naam + Leverancier
    Stap 2 — Eenheid (Gewicht / Stuks / Vloeistof)
    Stap 3 — Verpakkingsgrootte (label past zich aan op keuze stap 2)
    Stap 4 — Gebruiksfrequentie → vertaalt naar buffer_pct + vraag_per_cover hint
    Stap 5 — Geavanceerd (uitklapbaar, pre-filled)
    Stap 6 — Opslaan
    """
    from pathlib import Path

    # ── Constanten ────────────────────────────────────────────────────────
    EENHEID_LABELS = {
        "kg":    ("Gewicht (kg)",   "Zak / doos van"),
        "stuk":  ("Stuks",          "Doos van"),
        "liter": ("Vloeistof (L)",  "Verpakking van"),
    }
    EENHEID_SUFFIX = {"kg": "kg", "stuk": "stuks", "liter": "L"}

    GEBRUIK_OPTIES = {
        "Weinig":     {"buffer_pct": 0.15, "vraag_hint": 0.05,
                       "toelichting": "bijv. speciale sausen, weinig besteld"},
        "Normaal":    {"buffer_pct": 0.20, "vraag_hint": 0.10,
                       "toelichting": "meeste dagelijkse producten"},
        "Veel":       {"buffer_pct": 0.25, "vraag_hint": 0.20,
                       "toelichting": "bijv. friet, brood, drank"},
        "Heel veel":  {"buffer_pct": 0.30, "vraag_hint": 0.35,
                       "toelichting": "bijv. water, ketchup — bijna altijd nodig"},
    }

    SUPPLIER_TYPE_MAP = {
        "Hanos": "wholesale", "Vers Leverancier": "fresh",
        "Bakkersland": "bakery", "Heineken Distrib.": "beer", "Overig": "other",
    }

    # ── Haal leveranciers op uit de database ─────────────────────────────
    leveranciers_lijst = get_leveranciers_lijst(tenant_id)
    lev_namen = [l["naam"] for l in leveranciers_lijst] if leveranciers_lijst else list(SUPPLIER_TYPE_MAP.keys())

    # ── Initialiseer session_state sleutels ──────────────────────────────
    defaults = {
        "wiz_stap":          1,
        "wiz_naam":          "",
        "wiz_sku":           "",
        "wiz_leverancier":   lev_namen[0] if lev_namen else "Overig",
        "wiz_eenheid":       None,
        "wiz_pack_qty":      1.0,
        "wiz_gebruik":       None,
        "wiz_buffer_pct":    20,
        "wiz_vraag":         0.10,
        "wiz_min_stock":     1.0,
        "wiz_lead_time":     1,
        "wiz_perishability": "low",
        "wiz_open":          False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    stap = st.session_state.wiz_stap

    with st.expander("➕ Nieuw product toevoegen", expanded=st.session_state.wiz_open):

        # ── Voortgangsindicator ───────────────────────────────────────────
        stap_labels = ["Naam", "Eenheid", "Verpakking", "Gebruik", "Geavanceerd", "Opslaan"]
        cols_prog = st.columns(len(stap_labels))
        for i, label in enumerate(stap_labels, start=1):
            with cols_prog[i - 1]:
                if i < stap:
                    st.markdown(f"~~{label}~~ ✓")
                elif i == stap:
                    st.markdown(f"**{label}**")
                else:
                    st.markdown(f"<span style='color:#aaa'>{label}</span>", unsafe_allow_html=True)
        st.divider()

        # ════════════════════════════════════════════════════════════════
        # STAP 1 — Naam + Leverancier
        # ════════════════════════════════════════════════════════════════
        if stap == 1:
            st.markdown("### Hoe heet het product en bij welke leverancier?")
            st.caption("Gebruik de naam zoals hij op de factuur of in het ordersysteem staat.")

            naam = st.text_input(
                "Productnaam",
                value=st.session_state.wiz_naam,
                placeholder="bijv. Friet diepvries 9mm",
            )
            sku = st.text_input(
                "SKU-code (artikelnummer)",
                value=st.session_state.wiz_sku,
                placeholder="bijv. SKU-031",
                help="De code zoals de leverancier hem gebruikt. Wordt automatisch hoofdletters.",
            )
            lev = st.selectbox(
                "Leverancier",
                options=lev_namen,
                index=lev_namen.index(st.session_state.wiz_leverancier)
                      if st.session_state.wiz_leverancier in lev_namen else 0,
            )

            if st.button("Volgende →", type="primary", key="wiz_btn_1"):
                errors = []
                if not naam.strip():
                    errors.append("Vul een productnaam in.")
                if not sku.strip():
                    errors.append("Vul een SKU-code in.")
                if sku.strip().upper() in df_producten["id"].values:
                    errors.append(f"SKU **{sku.strip().upper()}** bestaat al.")
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    st.session_state.wiz_naam       = naam.strip()
                    st.session_state.wiz_sku        = sku.strip().upper()
                    st.session_state.wiz_leverancier = lev
                    st.session_state.wiz_stap       = 2
                    st.session_state.wiz_open       = True
                    st.rerun()

        # ════════════════════════════════════════════════════════════════
        # STAP 2 — Eenheid
        # ════════════════════════════════════════════════════════════════
        elif stap == 2:
            st.markdown(f"### Hoe wordt **{st.session_state.wiz_naam}** gemeten?")
            st.caption("Kies hoe jij dit product telt of weegt bij ontvangst en inventaris.")

            col_a, col_b, col_c = st.columns(3)
            keuze = None
            with col_a:
                if st.button("⚖️ Gewicht (kg)", use_container_width=True, key="wiz_eenheid_kg"):
                    keuze = "kg"
            with col_b:
                if st.button("📦 Stuks", use_container_width=True, key="wiz_eenheid_stuk"):
                    keuze = "stuk"
            with col_c:
                if st.button("🧴 Vloeistof (L)", use_container_width=True, key="wiz_eenheid_liter"):
                    keuze = "liter"

            if keuze:
                st.session_state.wiz_eenheid = keuze
                st.session_state.wiz_stap    = 3
                st.session_state.wiz_open    = True
                st.rerun()

            st.button("← Terug", key="wiz_terug_2", on_click=lambda: st.session_state.update({"wiz_stap": 1}))

        # ════════════════════════════════════════════════════════════════
        # STAP 3 — Verpakkingsgrootte
        # ════════════════════════════════════════════════════════════════
        elif stap == 3:
            eenheid     = st.session_state.wiz_eenheid
            prefix      = EENHEID_LABELS[eenheid][1]
            suffix      = EENHEID_SUFFIX[eenheid]

            st.markdown(f"### Hoe groot is één verpakking?")
            st.caption(
                f"Één besteleenheid bij de leverancier — bijv. '{prefix} 10 {suffix}'. "
                "Dit bepaalt hoe het besteladvies wordt afgerond."
            )

            pack_qty = st.number_input(
                f"{prefix} ___ {suffix}",
                min_value=0.1,
                value=float(st.session_state.wiz_pack_qty),
                step=1.0 if eenheid == "stuk" else 0.5,
                format="%.0f" if eenheid == "stuk" else "%.1f",
            )

            col_v, col_t = st.columns([1, 5])
            with col_v:
                if st.button("Volgende →", type="primary", key="wiz_btn_3"):
                    st.session_state.wiz_pack_qty = pack_qty
                    st.session_state.wiz_min_stock = pack_qty  # pre-fill stap 5
                    st.session_state.wiz_stap     = 4
                    st.session_state.wiz_open     = True
                    st.rerun()
            with col_t:
                st.button("← Terug", key="wiz_terug_3", on_click=lambda: st.session_state.update({"wiz_stap": 2}))

        # ════════════════════════════════════════════════════════════════
        # STAP 4 — Gebruiksfrequentie
        # ════════════════════════════════════════════════════════════════
        elif stap == 4:
            st.markdown(f"### Hoe vaak gebruiken jullie **{st.session_state.wiz_naam}**?")
            st.caption(
                "Dit bepaalt hoeveel buffer het systeem inbouwt. "
                "Je kunt dit later altijd verfijnen via Geavanceerd."
            )

            for label, data in GEBRUIK_OPTIES.items():
                col_btn, col_uitleg = st.columns([1, 4])
                with col_btn:
                    if st.button(label, use_container_width=True, key=f"wiz_gebruik_{label}"):
                        st.session_state.wiz_gebruik    = label
                        st.session_state.wiz_buffer_pct = int(data["buffer_pct"] * 100)
                        st.session_state.wiz_vraag      = data["vraag_hint"]
                        st.session_state.wiz_stap       = 5
                        st.session_state.wiz_open       = True
                        st.rerun()
                with col_uitleg:
                    st.caption(f"Buffer {int(data['buffer_pct']*100)}% — {data['toelichting']}")

            st.button("← Terug", key="wiz_terug_4", on_click=lambda: st.session_state.update({"wiz_stap": 3}))

        # ════════════════════════════════════════════════════════════════
        # STAP 5 — Geavanceerd (uitklapbaar, pre-filled)
        # ════════════════════════════════════════════════════════════════
        elif stap == 5:
            eenheid = st.session_state.wiz_eenheid
            suffix  = EENHEID_SUFFIX[eenheid]

            st.markdown(f"### Bijna klaar — controleer de instellingen")
            st.caption(
                f"Op basis van jouw keuze (**{st.session_state.wiz_gebruik}**) "
                "hebben we de waarden ingevuld. Pas aan als nodig."
            )

            col_l, col_r = st.columns(2)
            with col_l:
                buffer_pct_input = st.number_input(
                    "Buffer % (veiligheidsmarge)",
                    min_value=0, max_value=100,
                    value=st.session_state.wiz_buffer_pct,
                    help="Hoeveel procent extra inkopen bovenop de verwachte vraag.",
                )
                vraag_input = st.number_input(
                    f"Gemiddeld verbruik per gast ({suffix})",
                    min_value=0.0,
                    value=float(st.session_state.wiz_vraag),
                    step=0.01, format="%.3f",
                    help="Hoeveel van dit product gebruik je gemiddeld per couvert.",
                )
            with col_r:
                min_stock_input = st.number_input(
                    f"Minimale voorraad ({suffix})",
                    min_value=0.0,
                    value=float(st.session_state.wiz_min_stock),
                    step=float(st.session_state.wiz_pack_qty),
                    help="Nooit minder dan dit op voorraad — ook als de vraag laag is.",
                )
                lead_time_input = st.number_input(
                    "Levertijd (dagen)",
                    min_value=1, max_value=14,
                    value=st.session_state.wiz_lead_time,
                    help="Hoeveel dagen na bestelling levert deze leverancier?",
                )

            with st.expander("Meer instellingen (houdbaarheid, afronden)", expanded=False):
                perishability_input = st.selectbox(
                    "Houdbaarheid",
                    options=["low", "medium", "high"],
                    index=["low", "medium", "high"].index(st.session_state.wiz_perishability),
                    format_func=lambda x: {
                        "low":    "Laag — diepvries of droog (weken/maanden)",
                        "medium": "Midden — gekoeld (dagen)",
                        "high":   "Hoog — vers, dag vers",
                    }[x],
                )
                round_to_pack = st.selectbox(
                    "Afronden op hele verpakking?",
                    options=[1, 0],
                    format_func=lambda x: "Ja — altijd hele dozen/zakken bestellen" if x == 1 else "Nee",
                )

            col_v, col_t = st.columns([1, 5])
            with col_v:
                if st.button("Verder →", type="primary", key="wiz_btn_5"):
                    st.session_state.wiz_buffer_pct    = buffer_pct_input
                    st.session_state.wiz_vraag         = vraag_input
                    st.session_state.wiz_min_stock     = min_stock_input
                    st.session_state.wiz_lead_time     = lead_time_input
                    st.session_state.wiz_perishability = perishability_input
                    st.session_state.wiz_round_to_pack = round_to_pack
                    st.session_state.wiz_stap          = 6
                    st.session_state.wiz_open          = True
                    st.rerun()
            with col_t:
                st.button("← Terug", key="wiz_terug_5", on_click=lambda: st.session_state.update({"wiz_stap": 4}))

        # ════════════════════════════════════════════════════════════════
        # STAP 6 — Samenvatting + Opslaan
        # ════════════════════════════════════════════════════════════════
        elif stap == 6:
            eenheid = st.session_state.wiz_eenheid
            suffix  = EENHEID_SUFFIX[eenheid]
            lev_naam = st.session_state.wiz_leverancier

            st.markdown(f"### Klopt alles? Dan slaan we het op.")

            samenvatting = {
                "Productnaam":        st.session_state.wiz_naam,
                "SKU-code":           st.session_state.wiz_sku,
                "Leverancier":        lev_naam,
                "Eenheid":            eenheid,
                "Verpakkingsgrootte": f"{st.session_state.wiz_pack_qty} {suffix}",
                "Gebruik":            st.session_state.wiz_gebruik,
                "Buffer":             f"{st.session_state.wiz_buffer_pct}%",
                "Verbruik/gast":      f"{st.session_state.wiz_vraag:.3f} {suffix}",
                "Min. voorraad":      f"{st.session_state.wiz_min_stock} {suffix}",
                "Levertijd":          f"{st.session_state.wiz_lead_time} dag(en)",
            }
            for k, v in samenvatting.items():
                st.markdown(f"- **{k}:** {v}")

            col_op, col_t = st.columns([1, 5])
            with col_op:
                if st.button("✅ Product opslaan", type="primary", key="wiz_opslaan"):
                    products_path = Path(__file__).parent / "demo_data" / "products.csv"

                    # Bepaal supplier_type op basis van naam uit de DB-lijst
                    # (valt terug op SUPPLIER_TYPE_MAP als leveranciersnaam bekende alias is)
                    sup_type = SUPPLIER_TYPE_MAP.get(lev_naam, "other")

                    nieuwe_rij = {
                        "sku_id":           st.session_state.wiz_sku,
                        "sku_name":         st.session_state.wiz_naam,
                        "base_unit":        eenheid,
                        "pack_qty":         st.session_state.wiz_pack_qty,
                        "pack_unit":        eenheid,
                        "perishability":    st.session_state.wiz_perishability,
                        "supplier_type":    sup_type,
                        "demand_per_cover": round(float(st.session_state.wiz_vraag), 4),
                        "buffer_pct":       round(st.session_state.wiz_buffer_pct / 100, 2),
                        "min_stock":        st.session_state.wiz_min_stock,
                        "round_to_pack":    st.session_state.get("wiz_round_to_pack", 1),
                        "lead_time_days":   st.session_state.wiz_lead_time,
                    }

                    df_bestaand = pd.read_csv(products_path)
                    df_bestaand = pd.concat(
                        [df_bestaand, pd.DataFrame([nieuwe_rij])], ignore_index=True
                    )
                    df_bestaand.to_csv(products_path, index=False)

                    get_products.clear()
                    _wizard_reset()
                    st.success(
                        f"Product **{nieuwe_rij['sku_name']}** ({nieuwe_rij['sku_id']}) "
                        f"opgeslagen onder **{lev_naam}**."
                    )
                    st.rerun()

            with col_t:
                st.button("← Terug", key="wiz_terug_6", on_click=lambda: st.session_state.update({"wiz_stap": 5}))


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

    # ── Nieuw product toevoegen — wizard ────────────────────────────────────
    st.divider()
    _wizard_nieuw_product(tenant_id, df)


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


# ── Scherm 8 — Instellingen (manager + admin) ─────────────────────────────
def page_instellingen() -> None:
    """Leveranciersbeheer + gebruikersbeheer voor de eigen tenant."""
    tenant_id = st.session_state.tenant_id

    if st.session_state.user_rol not in ("admin", "manager"):
        st.error("Geen toegang.")
        return

    st.title("Instellingen")
    st.caption(
        "Beheer de leveranciers en medewerkers van jouw restaurant. "
        "Stel leverdagen en e-mailadressen in per leverancier."
    )

    tab_lev, tab_gebr = st.tabs(["Leveranciers", "Gebruikers"])

    # ── Tab 1: Leveranciers ──────────────────────────────────────────────
    with tab_lev:
        st.subheader("Leveranciers & leveringsschema")
        st.caption(
            "Vink aan op welke dag elke leverancier levert. "
            "De besteltool gebruikt dit om automatisch voor het juiste aantal dagen te bestellen."
        )

        leveranciers = get_leveranciers_lijst(tenant_id)
        DAGLETTERS   = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
        DAG_KOLOMMEN = ["levert_ma", "levert_di", "levert_wo", "levert_do",
                        "levert_vr", "levert_za", "levert_zo"]

        if not leveranciers:
            st.info("Nog geen leveranciers. Voeg ze toe via het formulier hieronder.")
        else:
            for lev in leveranciers:
                leverdagen_str = " · ".join(
                    DAGLETTERS[i]
                    for i, k in enumerate(DAG_KOLOMMEN)
                    if lev.get(k, False)
                ) or "geen leverdagen"
                email_badge = lev.get("email") or "geen e-mail"

                with st.expander(
                    f"**{lev['name']}** — {leverdagen_str} — {email_badge}",
                    expanded=False,
                ):
                    with st.form(f"form_lev_edit_{lev['id']}"):
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            naam_in   = st.text_input("Naam leverancier", value=lev["name"])
                            email_in  = st.text_input("E-mailadres", value=lev.get("email", ""),
                                                      placeholder="inkoop@leverancier.nl")
                            aanhef_in = st.text_input("Aanhef in e-mail", value=lev.get("aanhef", "Beste leverancier,"))
                        with c2:
                            lt_in = st.number_input(
                                "Levertijd (dagen)",
                                min_value=1, max_value=14,
                                value=int(lev.get("lead_time_days", 1)),
                                help="Hoeveel dagen duurt het van bestelling tot levering?",
                            )

                        st.markdown("**Leverdagen** — vink aan op welke dagen deze leverancier levert:")
                        dag_cols = st.columns(7)
                        levert_waarden = []
                        for i, (dagletter, dagkolom) in enumerate(zip(DAGLETTERS, DAG_KOLOMMEN)):
                            levert_waarden.append(
                                dag_cols[i].checkbox(dagletter, value=bool(lev.get(dagkolom, False)),
                                                     key=f"lev_{lev['id']}_{dagkolom}")
                            )

                        col_save, col_del = st.columns([3, 1])
                        with col_save:
                            opslaan = st.form_submit_button("Opslaan", type="primary", use_container_width=True)
                        with col_del:
                            verwijder = st.form_submit_button("Verwijder", use_container_width=True)

                    if opslaan:
                        ok, fout = db.update_leverancier(
                            lev["id"], naam_in, email_in, aanhef_in, lt_in,
                            *levert_waarden
                        )
                        if ok:
                            st.success(f"**{naam_in}** opgeslagen.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Opslaan mislukt: {fout}")

                    if verwijder:
                        ok, fout = db.verwijder_leverancier(lev["id"])
                        if ok:
                            st.success(f"**{lev['name']}** verwijderd.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Verwijderen mislukt: {fout}")

        st.divider()
        with st.expander("➕ Nieuwe leverancier toevoegen", expanded=not leveranciers):
            with st.form("form_nieuwe_leverancier", clear_on_submit=True):
                c1, c2 = st.columns([2, 1])
                with c1:
                    nieuw_naam   = st.text_input("Naam leverancier *", placeholder="bijv. Sligro")
                    nieuw_email  = st.text_input("E-mailadres", placeholder="inkoop@sligro.nl")
                    nieuw_aanhef = st.text_input("Aanhef", value="Beste leverancier,")
                with c2:
                    nieuw_lt = st.number_input("Levertijd (dagen)", min_value=1, max_value=14, value=1)

                st.markdown("**Leverdagen:**")
                nd_cols = st.columns(7)
                nieuwe_dagen = [
                    nd_cols[i].checkbox(DAGLETTERS[i], key=f"nieuw_dag_{i}")
                    for i in range(7)
                ]

                if st.form_submit_button("Leverancier aanmaken", type="primary"):
                    if not nieuw_naam.strip():
                        st.error("Naam is verplicht.")
                    elif not any(nieuwe_dagen):
                        st.error("Selecteer minimaal 1 leverdag.")
                    else:
                        ok, fout = db.maak_leverancier_aan(
                            tenant_id, nieuw_naam, nieuw_email, nieuw_aanhef, nieuw_lt,
                            *nieuwe_dagen
                        )
                        if ok:
                            st.success(f"Leverancier **{nieuw_naam}** aangemaakt.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Aanmaken mislukt: {fout}")

    # ── Tab 2: Gebruikers ────────────────────────────────────────────────
    with tab_gebr:
        st.subheader("Medewerkers")
        st.caption(
            "Maak medewerkers aan met rol 'Medewerker'. "
            "Je kunt per medewerker aangeven wat ze mogen doen."
        )

        RECHTEN_LABELS = {
            "voorraad_wijzigen": "Voorraad handmatig wijzigen",
            "orders_versturen":  "Bestellingen goedkeuren & versturen",
            "acties":            "Acties / campagnes aanmaken",
            "recepten_beheren":  "Recepten beheren",
        }

        # Haal alle gebruikers van deze tenant op
        alle_gebruikers = db.laad_alle_gebruikers()
        tenant_gebruikers = [g for g in alle_gebruikers if g["tenant_id"] == tenant_id]
        ingelogde_user = st.session_state.get("user_naam", "")

        # Managers mogen alleen 'user' rol aanmaken (geen admin)
        is_admin = st.session_state.user_rol == "admin"

        if not tenant_gebruikers:
            st.info("Nog geen medewerkers aangemaakt.")
        else:
            for g in tenant_gebruikers:
                if g["role"] == "admin" and not is_admin:
                    continue  # managers zien geen admin accounts
                rol_label = {"admin": "Admin", "manager": "Manager", "user": "Medewerker"}.get(g["role"], g["role"])
                with st.expander(f"**{g['username']}** · {g.get('full_name', '')} · {rol_label}"):
                    with st.form(f"form_gebr_edit_{g['id']}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            nieuwe_uname = st.text_input("Gebruikersnaam", value=g["username"])
                            nieuwe_fnaam = st.text_input("Volledige naam", value=g.get("full_name", ""))
                        with c2:
                            nieuw_pw = st.text_input("Nieuw wachtwoord", type="password",
                                                     placeholder="Laat leeg om niet te wijzigen")
                            rol_opties = (["user", "manager", "admin"] if is_admin
                                          else ["user", "manager"])
                            rol_idx    = rol_opties.index(g["role"]) if g["role"] in rol_opties else 0
                            nieuwe_rol = st.selectbox("Rol", rol_opties,
                                                      format_func=lambda r: {"admin": "Admin",
                                                                              "manager": "Manager",
                                                                              "user": "Medewerker"}[r],
                                                      index=rol_idx)

                        # Permissies tonen alleen voor 'user' rol
                        if g["role"] == "user":
                            st.markdown("**Rechten voor deze medewerker:**")
                            huidige_rechten = g.get("permissions") or {}
                            perm_cols = st.columns(2)
                            nieuwe_rechten = {}
                            for pi, (perm_key, perm_label) in enumerate(RECHTEN_LABELS.items()):
                                col = perm_cols[pi % 2]
                                nieuwe_rechten[perm_key] = col.checkbox(
                                    perm_label,
                                    value=bool(huidige_rechten.get(perm_key, False)),
                                    key=f"perm_{g['id']}_{perm_key}",
                                )
                        else:
                            nieuwe_rechten = None  # admin/manager hebben altijd alle rechten

                        if st.form_submit_button("Opslaan", type="primary"):
                            if not nieuwe_uname.strip():
                                st.error("Gebruikersnaam mag niet leeg zijn.")
                            else:
                                ok, fout = db.update_gebruiker(
                                    g["id"], nieuwe_uname.strip(),
                                    nieuwe_fnaam.strip(), nieuwe_rol,
                                    nieuw_pw or None,
                                )
                                if ok and nieuwe_rechten is not None:
                                    db.update_gebruiker_rechten(g["id"], nieuwe_rechten)
                                if ok:
                                    st.success("Gegevens bijgewerkt.")
                                    st.rerun()
                                else:
                                    st.error(f"Opslaan mislukt: {fout}")

                    if g["username"] != ingelogde_user:
                        confirm_key = f"confirm_del_gebr_{g['id']}"
                        if st.session_state.get(confirm_key):
                            st.warning(f"Verwijder **{g['username']}**?")
                            col_ja, col_nee = st.columns(2)
                            with col_ja:
                                if st.button("Ja, verwijder", key=f"ja_g_{g['id']}", type="primary"):
                                    ok, _ = db.verwijder_gebruiker(g["id"])
                                    if ok:
                                        st.session_state.pop(confirm_key, None)
                                        st.success(f"{g['username']} verwijderd.")
                                        st.rerun()
                            with col_nee:
                                if st.button("Annuleren", key=f"nee_g_{g['id']}"):
                                    st.session_state.pop(confirm_key, None)
                                    st.rerun()
                        else:
                            if st.button("Verwijder medewerker", key=f"del_g_{g['id']}"):
                                st.session_state[confirm_key] = True
                                st.rerun()

        st.divider()
        st.subheader("Nieuwe medewerker toevoegen")
        with st.form("form_nieuw_gebr_inst", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nw_uname = st.text_input("Gebruikersnaam *")
                nw_fnaam = st.text_input("Volledige naam")
            with c2:
                nw_pw  = st.text_input("Wachtwoord *", type="password")
                nw_rol = st.selectbox(
                    "Rol",
                    ["user", "manager"] if not is_admin else ["user", "manager", "admin"],
                    format_func=lambda r: {"admin": "Admin",
                                           "manager": "Manager",
                                           "user": "Medewerker"}[r],
                )

            # Permissies voor nieuwe medewerker (standaard alles uit)
            st.markdown("**Rechten (alleen van toepassing bij rol Medewerker):**")
            perm_cols_nw = st.columns(2)
            nw_rechten = {}
            for pi, (perm_key, perm_label) in enumerate(RECHTEN_LABELS.items()):
                nw_rechten[perm_key] = perm_cols_nw[pi % 2].checkbox(
                    perm_label, value=False, key=f"nw_perm_{perm_key}"
                )

            if st.form_submit_button("Medewerker aanmaken", type="primary"):
                if not nw_uname.strip() or not nw_pw:
                    st.error("Gebruikersnaam en wachtwoord zijn verplicht.")
                else:
                    rechten = nw_rechten if nw_rol == "user" else {}
                    gelukt = db.maak_gebruiker_aan(
                        tenant_id, nw_uname.strip(), nw_pw,
                        nw_rol, nw_fnaam.strip(), rechten,
                    )
                    if gelukt:
                        st.success(f"Medewerker **{nw_uname.strip()}** aangemaakt.")
                        st.rerun()
                    else:
                        st.error("Aanmaken mislukt — gebruikersnaam bestaat mogelijk al.")


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
                    rol = st.selectbox("Rol", ["user", "manager", "admin"],
                                      format_func=lambda r: {"admin": "Admin",
                                                              "manager": "Manager",
                                                              "user": "Medewerker"}[r])

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

        nav_opties  = _nav_paginas()
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
    elif scherm == PAGE_INSTELLINGEN:
        page_instellingen()
    elif scherm == PAGE_ADMIN:
        page_admin()
    else:
        page_leerrapport()


main()
