"""Restaurant Forecast & Besteladvies — multi-tenant versie."""
from __future__ import annotations
import time
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import state
import data_loader as dl
import forecast as fc
import recommendation as rc
import learning
import weather as wt
import inventory as inv
import db
import permissions as perm
import monitoring  # Sentry + structlog — moet als eerste na stdlib imports
import email_service as mail
from cache import (
    get_products, get_sales_history, get_events, get_stock_count,
    get_leveranciers_dict, get_leveranciers_lijst,
    get_reservations,
)

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
PAGE_ADMIN        = "Beheer"         # Uitsluitend super_admin: cross-tenant klantbeheer

WEEKDAGEN        = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
CONFIDENCE_LABEL = {"hoog": "Hoog", "gemiddeld": "Gemiddeld", "laag": "Laag"}

# Pagina's per rol
_PAGINAS_BASIS      = [PAGE_CLOSING, PAGE_FORECAST, PAGE_REVIEW, PAGE_EXPORT,
                       PAGE_INVENTARIS, PAGE_PRODUCTEN, PAGE_LEERRAPPORT]
PAGINAS             = _PAGINAS_BASIS                                                 # user (read-only)
PAGINAS_MANAGER     = _PAGINAS_BASIS + [PAGE_INSTELLINGEN]                           # manager
PAGINAS_ADMIN       = _PAGINAS_BASIS + [PAGE_INSTELLINGEN]                           # admin (tenant-level)
PAGINAS_SUPER_ADMIN = _PAGINAS_BASIS + [PAGE_INSTELLINGEN, PAGE_ADMIN]               # super_admin (platform-level)


def _nav_paginas() -> list[str]:
    """Geeft de navigatielijst terug op basis van de rol van de ingelogde gebruiker."""
    rol = st.session_state.get("user_rol", "user")
    if rol == "super_admin":
        return PAGINAS_SUPER_ADMIN
    if rol == "admin":
        return PAGINAS_ADMIN
    if rol == "manager":
        return PAGINAS_MANAGER
    return PAGINAS


def _heeft_recht(recht: str) -> bool:
    """True als de ingelogde gebruiker het opgegeven recht heeft."""
    rol   = st.session_state.get("user_rol", "user")
    perms = st.session_state.get("user_permissions", {})
    return perm.heeft_recht(recht, rol, perms)


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


# ── Gecachte data — zie cache.py ──────────────────────────────────────────


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
            tenant_slug = st.text_input(
                "Restaurant",
                value="",
                placeholder="bijv. jouw-restaurant",
                help="De korte naam (slug) van jouw restaurant — aangeleverd bij onboarding.",
            )
            gebruiker  = st.text_input("Gebruikersnaam")
            wachtwoord = st.text_input("Wachtwoord", type="password")
            inloggen   = st.form_submit_button(
                "Inloggen", use_container_width=True, type="primary"
            )

        if inloggen:
            if not tenant_slug.strip() or not gebruiker.strip() or not wachtwoord:
                st.error("Vul Restaurant, Gebruikersnaam en Wachtwoord in.")
                return
            user = db.verificeer_gebruiker(tenant_slug.strip(), gebruiker, wachtwoord)
            if user:
                st.session_state.ingelogd             = True
                st.session_state.tenant_id            = user["tenant_id"]
                st.session_state.tenant_naam          = user["tenant_naam"]
                st.session_state.tenant_slug          = tenant_slug.strip()
                st.session_state.user_naam            = user["username"]
                st.session_state.user_rol             = user["role"]
                st.session_state.user_permissions     = user.get("permissions", {})
                st.session_state["_login_timestamp"]  = time.time()
                st.rerun()
            else:
                st.error("Restaurant, gebruikersnaam of wachtwoord klopt niet.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Wachtwoord vergeten?", use_container_width=True, type="secondary"):
            st.session_state["_show_reset"] = True
            st.rerun()


# ── Scherm 1 — Dag afsluiten ────────────────────────────────────────────
from views.page_closing import render as page_closing


# ── Scherm 2 — Forecast morgen ──────────────────────────────────────────
from views.page_forecast import render as page_forecast


# ── Scherm 3 — Bestelreview ──────────────────────────────────────────────
from views.page_review import render as page_review


# ── Scherm 4 — Export ────────────────────────────────────────────────────
from views.page_export import render as page_export

# ── Scherm 5 — Inventaris ─────────────────────────────────────────────────
from views.page_inventaris import render as page_inventaris


# ── Scherm 6 — Producten & Leveranciers ──────────────────────────────────
from views.page_producten import render as page_producten


# ── Scherm 7 — Leerrapport ────────────────────────────────────────────────
from views.page_leerrapport import render as page_leerrapport


# ── Scherm 8 — Instellingen ──────────────────────────────────────────────
from views.page_instellingen import render as page_instellingen


# ── Admin ────────────────────────────────────────────────────────────────
from views.page_admin import render as page_admin

# ── Password reset ────────────────────────────────────────────────────────
from views.page_password_reset import render_aanvraag as page_reset_aanvraag
from views.page_password_reset import render_nieuw_wachtwoord as page_reset_nieuw


# ── Navigatie ──────────────────────────────────────────────────────────────
def _check_startup_config() -> None:
    """Controleer kritieke configuratie eenmalig per sessie en log ontbrekende keys."""
    if st.session_state.get("_startup_checked"):
        return
    st.session_state["_startup_checked"] = True

    resend_key = (
        st.secrets.get("resend", {}).get("api_key")
        if hasattr(st, "secrets") else None
    )
    if not resend_key:
        monitoring.log_error(
            "startup_config_ontbreekt",
            hint="RESEND_API_KEY niet gevonden in secrets — e-mail verzenden werkt niet",
        )


def main() -> None:
    _css()
    init_state()
    _check_startup_config()

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

    # Password reset via URL-token (vóór login-check — gebruiker is uitgelogd)
    reset_token = st.query_params.get("token")
    if reset_token:
        page_reset_nieuw(reset_token)
        return

    if not st.session_state.ingelogd:
        # Toon reset-aanvraag als gebruiker op "Wachtwoord vergeten?" heeft geklikt
        if st.session_state.get("_show_reset"):
            page_reset_aanvraag()
            st.markdown("<br>", unsafe_allow_html=True)
            col_l, col_m, col_r = st.columns([1, 1.4, 1])
            with col_m:
                if st.button("← Terug naar inloggen", use_container_width=True):
                    st.session_state.pop("_show_reset", None)
                    st.rerun()
            return

        # Toon succesmelding na wachtwoord reset
        if st.session_state.pop("_reset_success", False):
            col_l, col_m, col_r = st.columns([1, 1.4, 1])
            with col_m:
                st.success("Wachtwoord succesvol gewijzigd. Log in met je nieuwe wachtwoord.")

        page_login()
        return

    SESSION_MAX_SECONDEN = 8 * 60 * 60  # 8 uur
    login_ts = st.session_state.get("_login_timestamp", 0)
    if time.time() - login_ts > SESSION_MAX_SECONDEN:
        state.clear_user()
        st.warning("Je sessie is verlopen. Log opnieuw in.")
        st.rerun()

    # Sentry context bijwerken bij elke render (paginawissel of herlaad)
    monitoring.stel_sentry_context_in(
        tenant_id = str(st.session_state.get("tenant_id", "")),
        user_naam = st.session_state.get("user_naam", ""),
        pagina    = st.session_state.get("pagina", ""),
    )

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
        # Defense-in-depth: ook al staat PAGE_ADMIN alleen in PAGINAS_SUPER_ADMIN,
        # iemand kan st.session_state.pagina direct zetten via een bug of exploit.
        if st.session_state.get("user_rol") != "super_admin":
            st.error("Geen toegang. Deze pagina is alleen voor super administrators.")
            return
        page_admin()
    else:
        page_leerrapport()


main()
