"""Restaurant Forecast & Besteladvies V1 — Family Maarssen demo."""
from __future__ import annotations
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import data_loader as dl
import forecast as fc
import recommendation as rc
import learning
import weather as wt

st.set_page_config(
    page_title="Besteltool — Family Maarssen",
    page_icon="🍟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inloggegevens ─────────────────────────────────────────────────────────
# Op Streamlit Cloud komen deze uit het Secrets-dashboard.
# Lokaal uit .streamlit/secrets.toml (staat in .gitignore).
def _laad_gebruikers() -> dict[str, str]:
    try:
        return dict(st.secrets["gebruikers"])
    except (KeyError, FileNotFoundError):
        return {"manager": "family2024", "admin": "besteltool!"}

GEBRUIKERS = _laad_gebruikers()

WEEKDAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
CONFIDENCE_ICON = {"hoog": "🟢", "gemiddeld": "🟡", "laag": "🔴"}
PAGINAS = [
    "📋  Dag afsluiten",
    "📊  Forecast morgen",
    "✅  Bestelreview",
    "📤  Export",
    "📈  Leerrapport",
]

# ── Gecachte data ──────────────────────────────────────────────────────────
@st.cache_data
def get_products() -> pd.DataFrame:
    return dl.load_products()

@st.cache_data
def get_sales_history() -> pd.DataFrame:
    return dl.load_sales_history()

@st.cache_data
def get_events() -> pd.DataFrame:
    return dl.load_events()

@st.cache_data
def get_stock_count() -> pd.DataFrame:
    return dl.load_stock_count()

@st.cache_data
def get_reservations() -> pd.DataFrame:
    return dl.load_reservations()

# ── Session state ──────────────────────────────────────────────────────────
def init_state() -> None:
    for key, val in {
        "ingelogd":       False,
        "closing_data":   None,
        "forecast_result":None,
        "advies_df":      None,
        "approved_orders":None,
        "pagina":         "📋  Dag afsluiten",
    }.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Inlogscherm ────────────────────────────────────────────────────────────
def page_login() -> None:
    col_l, col_m, col_r = st.columns([1, 1.4, 1])
    with col_m:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 🍟 Besteltool — Family Maarssen")
        st.caption("Log in om verder te gaan.")
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            gebruiker = st.text_input("Gebruikersnaam")
            wachtwoord = st.text_input("Wachtwoord", type="password")
            inloggen = st.form_submit_button(
                "Inloggen", use_container_width=True, type="primary"
            )

        if inloggen:
            if GEBRUIKERS.get(gebruiker) == wachtwoord:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Gebruikersnaam of wachtwoord klopt niet.")

# ── Overlay voor voltooide stappen ────────────────────────────────────────
def _toon_voltooid_overlay(page_key: str) -> None:
    """
    Rendert een reset-knop als eerste element, daarna CSS die de rest van de
    pagina dimt en niet-klikbaar maakt. Knop zelf blijft zichtbaar en klikbaar.
    """
    if st.button(
        "🔄  Opnieuw beginnen — reset alle stappen",
        type="secondary",
        use_container_width=True,
        key=f"reset_{page_key}",
    ):
        for k in ["closing_data", "forecast_result", "advies_df", "approved_orders"]:
            st.session_state[k] = None
        st.session_state.pagina = "📋  Dag afsluiten"
        st.rerun()

    st.markdown("""
    <style>
    /* Donkere overlay over de hoofdinhoud — sidebar blijft altijd vrij */
    .stMainBlockContainer > div:not(:first-child) {
        position: relative;
        pointer-events: none;
        user-select: none;
    }
    .stMainBlockContainer > div:not(:first-child)::after {
        content: "";
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.55);
        z-index: 999;
        pointer-events: none;
    }
    /* Sidebar nooit raken */
    [data-testid="stSidebar"] {
        pointer-events: auto !important;
        opacity: 1 !important;
        z-index: 1000;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Scherm 1 — Dag afsluiten ───────────────────────────────────────────────
def page_closing() -> None:
    if st.session_state.forecast_result is not None:
        _toon_voltooid_overlay("sluiting")
    st.title("📋  Dag afsluiten")
    st.caption("Vul de dagcijfers in. Het systeem berekent forecast en besteladvies.")

    df_producten  = get_products()
    df_stock_base = get_stock_count()
    df_events_all = get_events()
    df_res_all    = get_reservations()

    datum_vandaag = date.today()
    datum_morgen  = datum_vandaag + timedelta(days=1)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Vandaag")
        datum_vandaag = st.date_input("Datum", value=datum_vandaag, format="DD/MM/YYYY")
        datum_morgen  = datum_vandaag + timedelta(days=1)
        covers        = st.number_input("Bonnen vandaag", min_value=0, step=1, value=0,
                                        help="Totaal aantal orders/gasten vandaag")
        omzet         = st.number_input("Omzet vandaag (€)", min_value=0.0, step=50.0,
                                        value=0.0)

    with col2:
        st.subheader("Morgen")
        st.info(
            f"Forecast voor: **{WEEKDAGEN[datum_morgen.weekday()].capitalize()} "
            f"{datum_morgen.strftime('%d %B %Y')}**"
        )

        # Laad geplande reserveringen/platters voor morgen uit CSV als default
        morgen_str    = datum_morgen.isoformat()
        df_res_morgen = df_res_all[df_res_all["datum"] == morgen_str]
        default_rc    = int(df_res_morgen["reserved_covers"].sum()) if not df_res_morgen.empty else 0
        default_p25   = int(df_res_morgen["party_platters_25"].sum()) if not df_res_morgen.empty else 0
        default_p50   = int(df_res_morgen["party_platters_50"].sum()) if not df_res_morgen.empty else 0

        reserved_covers = st.number_input(
            "Reserveringen morgen (bonnen)",
            min_value=0, step=1, value=default_rc,
            help=(
                "Vaste vooruitbestellingen of groepen die al bevestigd zijn. "
                "Het systeem telt deze op bij het historisch gemiddelde — "
                "bij 400 reserveringen bovenop een gemiddelde van 265 wordt de forecast verhoogd. "
                "Laat op 0 staan als er niets gereserveerd is."
            ),
        )

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            platters_25 = st.number_input("Partycatering 25 st", min_value=0,
                                          step=1, value=default_p25)
        with col_p2:
            platters_50 = st.number_input("Partycatering 50 st", min_value=0,
                                          step=1, value=default_p50)

        if platters_25 or platters_50:
            st.info(
                f"Party platters → extra minisnacks: frikandellen, nuggets, bitterballen "
                f"(+{platters_25*25 + platters_50*50} stuks totaal)"
            )

        bijzonderheden = st.text_area("Bijzonderheden", height=68, value="",
                                      placeholder="bv. lunch dicht, terras open, grote groep geannuleerd")

        # Toon event voor morgen als preview
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
    st.subheader("Closing stock — 30 kritieke SKU's")
    st.caption("Pas de voorraad aan als die afwijkt van de laatste telling.")

    stock_map    = dict(zip(df_stock_base["product_id"], df_stock_base["hoeveelheid"]))
    stock_invoer = df_producten[["id", "naam", "leverancier", "eenheid"]].copy()
    stock_invoer["voorraad"] = stock_invoer["id"].map(stock_map).fillna(0.0)

    edited_stock = st.data_editor(
        stock_invoer,
        column_config={
            "id":        st.column_config.TextColumn("SKU",        disabled=True, width="small"),
            "naam":      st.column_config.TextColumn("Artikel",    disabled=True, width="medium"),
            "leverancier":st.column_config.TextColumn("Leverancier",disabled=True,width="medium"),
            "eenheid":   st.column_config.TextColumn("Eenheid",    disabled=True, width="small"),
            "voorraad":  st.column_config.NumberColumn("Voorraad", min_value=0.0, step=1.0,
                                                        width="small"),
        },
        hide_index=True,
        use_container_width=True,
        key="stock_editor",
    )

    # ── Werkelijk resultaat van gisteren invullen ──────────────────────────
    gisteren = datum_vandaag - timedelta(days=1)
    if learning.heeft_open_werkelijk(gisteren):
        st.divider()
        st.subheader("Werkelijk resultaat van gisteren")
        st.caption(
            f"Je hebt voor **{WEEKDAGEN[gisteren.weekday()]} "
            f"{gisteren.strftime('%d %B')}** nog geen werkelijk resultaat ingevuld. "
            "Dit helpt het systeem beter te voorspellen."
        )
        col_w1, col_w2, col_w3 = st.columns([2, 2, 1])
        with col_w1:
            werkelijk_covers = st.number_input(
                "Werkelijk aantal bonnen gisteren", min_value=0, step=1, value=0,
                key="werkelijk_covers"
            )
        with col_w2:
            werkelijk_omzet = st.number_input(
                "Werkelijke omzet gisteren (€)", min_value=0.0, step=50.0, value=0.0,
                key="werkelijk_omzet"
            )
        with col_w3:
            st.write("")
            st.write("")
            if st.button("Opslaan", key="btn_werkelijk"):
                if werkelijk_covers > 0:
                    opgeslagen = learning.log_werkelijk(
                        gisteren, int(werkelijk_covers), float(werkelijk_omzet)
                    )
                    if opgeslagen:
                        st.success("Resultaat opgeslagen. Forecast verbetert mee.")
                        st.cache_data.clear()
                        st.rerun()

    # ── Weerpreview voor morgen ────────────────────────────────────────────
    st.divider()
    st.subheader("Weer morgen")
    weer_preview = wt.get_weer_morgen(datum_morgen)
    if weer_preview["beschikbaar"]:
        icon = weer_preview["icon"]
        w_col1, w_col2, w_col3 = st.columns(3)
        w_col1.metric(
            f"{icon} Temperatuur",
            f"{weer_preview['temp_max']:.0f}°C",
        )
        w_col2.metric("Regenrisico", f"{weer_preview['precip_prob']}%")
        w_col3.metric("Terras factor", f"×{weer_preview['terras_factor']:.2f}")
        if weer_preview["terras_factor"] > 1.0:
            st.success(f"{icon} {weer_preview['label']}")
        else:
            st.info(f"{icon} {weer_preview['label']}")
    else:
        st.warning("Weerdata niet beschikbaar — geen terras-correctie toegepast.")

    st.divider()
    if st.button("Bereken forecast en besteladvies →", type="primary", use_container_width=True):
        if covers == 0:
            st.error("Vul het aantal bonnen van vandaag in.")
            return

        df_history = get_sales_history()
        df_events  = df_events_all
        df_res     = df_res_all

        result = fc.bereken_forecast(
            covers_vandaag  = int(covers),
            omzet_vandaag   = float(omzet),
            reserved_covers = int(reserved_covers),
            bijzonderheden  = bijzonderheden,
            df_history      = df_history,
            df_events       = df_events,
            df_reservations = df_res,
            datum_morgen    = datum_morgen,
            manager_override= None,
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
            platters_25     = int(platters_25),
            platters_50     = int(platters_50),
        )

        # ── Dag opslaan → systeem leert ───────────────────────────────────
        dl.sla_dag_op(datum_vandaag, int(covers), float(omzet),
                      int(reserved_covers), bijzonderheden)
        df_stock_save = edited_stock[["id","voorraad"]].rename(
            columns={"id":"product_id","voorraad":"hoeveelheid"}
        )
        dl.sla_stock_op(datum_vandaag, df_stock_save)

        # Forecast loggen voor accuracy-tracking
        learning.log_forecast(datum_morgen, result["forecast_covers"],
                              result["event_naam"], bijzonderheden)

        # Cache wissen zodat nieuwe data direct beschikbaar is
        st.cache_data.clear()

        st.session_state.closing_data    = {"datum_vandaag": datum_vandaag,
                                            "covers": covers, "omzet": omzet}
        st.session_state.forecast_result = result
        st.session_state.advies_df       = advies_df
        st.session_state.approved_orders = None
        st.session_state.pagina          = "📊  Forecast morgen"
        st.rerun()

# ── Scherm 2 — Forecast morgen ─────────────────────────────────────────────
def page_forecast() -> None:
    if st.session_state.approved_orders is not None:
        _toon_voltooid_overlay("forecast")
    st.title("📊  Forecast morgen")

    if st.session_state.forecast_result is None:
        st.warning("Sluit eerst de dag af.")
        if st.button("← Naar dag afsluiten"):
            st.session_state.pagina = "📋  Dag afsluiten"
            st.rerun()
        return

    r          = st.session_state.forecast_result
    datum_str  = WEEKDAGEN[r["weekdag_morgen"]].capitalize() + \
                 r["datum_morgen"].strftime(" %d %B %Y")
    confidence = r["confidence"]

    st.subheader(f"Forecast voor {datum_str}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Verwachte bonnen",   r["forecast_covers"],
                delta=f"{r['forecast_covers'] - r['baseline']:+.0f} vs baseline")
    col2.metric("Verwachte omzet",    f"€ {r['forecast_omzet']:,.0f}")
    col3.metric("Betrouwbaarheid",
                f"{CONFIDENCE_ICON[confidence]} {confidence.capitalize()}")
    col4.metric("Baseline (zelfde weekdag)", f"{r['baseline']:.0f}")

    if r["fries_mult"] > 1.0 or r["desserts_mult"] > 1.0:
        col_f, col_d = st.columns(2)
        if r["fries_mult"] > 1.0:
            col_f.metric("Friet ratio-multiplier", f"×{r['fries_mult']:.2f}",
                         help="SKU-001 en SKU-002 worden extra verhoogd")
        if r["desserts_mult"] > 1.0:
            col_d.metric("Dessert ratio-multiplier", f"×{r['desserts_mult']:.2f}",
                         help="Softijs en milkshake worden extra verhoogd")

    if r["platters_25"] or r["platters_50"]:
        st.info(
            f"Partycatering morgen: **{r['platters_25']}× platter 25st** + "
            f"**{r['platters_50']}× platter 50st** → extra minisnack-vraag verwerkt"
        )

    # Weerkaart
    weer = r.get("weer", {})
    if weer.get("beschikbaar"):
        tf = weer["terras_factor"]
        df = weer["drinks_factor"]
        kleur = "success" if tf > 1.0 else "info"
        bericht = (
            f"{weer['icon']} **{weer['omschrijving']}** — "
            f"{weer['temp_max']:.0f}°C, {weer['precip_prob']}% regenrisico  \n"
            f"Terras-effect: covers ×{tf:.2f} | dranken ×{df:.2f}"
        )
        if kleur == "success":
            st.success(bericht)
        else:
            st.info(bericht)

    st.divider()
    st.subheader("Hoe is dit berekend?")
    for driver in r["drivers"]:
        st.write(f"• {driver}")

    if r["event_naam"] != "geen event":
        st.warning(f"Event actief: **{r['event_naam']}**")
    if confidence == "laag":
        st.error("Weinig historische data voor deze weekdag — extra aandacht bij review.")

    # Lerende correctie zichtbaar maken
    cf = r.get("correctie_factor", 1.0)
    if cf != 1.0:
        richting = "omhoog" if cf > 1.0 else "omlaag"
        st.info(
            f"Lerende correctie actief: systeem past forecast {richting} "
            f"(factor {cf:.3f}) op basis van eerdere dagresultaten. "
            f"[Zie leerrapport →]"
        )

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("← Aanpassen", use_container_width=True):
            st.session_state.pagina = "📋  Dag afsluiten"
            st.rerun()
    with col_b:
        if st.button("Naar bestelreview →", type="primary", use_container_width=True):
            st.session_state.pagina = "✅  Bestelreview"
            st.rerun()

# ── Scherm 3 — Bestelreview ────────────────────────────────────────────────
def page_review() -> None:
    if st.session_state.approved_orders is not None:
        _toon_voltooid_overlay("review")
    st.title("✅  Bestelreview")

    if st.session_state.advies_df is None:
        st.warning("Bereken eerst de forecast.")
        if st.button("← Naar dag afsluiten"):
            st.session_state.pagina = "📋  Dag afsluiten"
            st.rerun()
        return

    r         = st.session_state.forecast_result
    advies_df = st.session_state.advies_df.copy()

    st.caption(
        f"Forecast: **{r['forecast_covers']} bonnen** — pas alleen uitzonderingen aan."
    )

    n_bestellen = int((advies_df["besteladvies"] > 0).sum())
    col1, col2, col3 = st.columns(3)
    col1.metric("Te bestellen",        n_bestellen)
    col2.metric("Voldoende in stock",  len(advies_df) - n_bestellen)
    col3.metric("Leveranciers",
                advies_df[advies_df["besteladvies"] > 0]["leverancier"].nunique())

    st.divider()

    weergave = advies_df.rename(columns={
        "id":             "SKU",
        "naam":           "Artikel",
        "leverancier":    "Leverancier",
        "eenheid":        "Eenheid",
        "voorraad":       "Voorraad",
        "verwachte_vraag":"Verwachte vraag",
        "buffer_qty":     "Buffer",
        "platter_extra":  "Party extra",
        "besteladvies":   "Bestellen",
        "reden":          "Reden",
    })

    edited = st.data_editor(
        weergave.drop(columns=["SKU"]),
        column_config={
            "Artikel":        st.column_config.TextColumn(disabled=True, width="medium"),
            "Leverancier":    st.column_config.TextColumn(disabled=True, width="medium"),
            "Eenheid":        st.column_config.TextColumn(disabled=True, width="small"),
            "Voorraad":       st.column_config.NumberColumn(disabled=True, format="%.1f",width="small"),
            "Verwachte vraag":st.column_config.NumberColumn(disabled=True, format="%.1f",width="small"),
            "Buffer":         st.column_config.NumberColumn(disabled=True, format="%.1f",width="small"),
            "Party extra":    st.column_config.NumberColumn(disabled=True, format="%.0f",width="small"),
            "Bestellen":      st.column_config.NumberColumn(min_value=0.0, step=1.0, width="small"),
            "Reden":          st.column_config.TextColumn(disabled=True, width="large"),
        },
        hide_index=True,
        use_container_width=True,
        key="review_editor",
    )

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("← Terug naar forecast", use_container_width=True):
            st.session_state.pagina = "📊  Forecast morgen"
            st.rerun()
    with col_b:
        if st.button("Goedkeuren en exporteren →", type="primary", use_container_width=True):
            approved = advies_df.copy()
            approved["besteladvies"] = edited["Bestellen"].values
            st.session_state.approved_orders = approved
            st.session_state.pagina = "📤  Export"
            st.rerun()

# ── Scherm 4 — Export ─────────────────────────────────────────────────────
def page_export() -> None:
    st.title("📤  Export — Bestellijst per leverancier")

    if st.session_state.approved_orders is None:
        st.warning("Keur eerst het besteladvies goed.")
        if st.button("← Naar bestelreview"):
            st.session_state.pagina = "✅  Bestelreview"
            st.rerun()
        return

    r        = st.session_state.forecast_result
    approved = st.session_state.approved_orders
    datum    = r["datum_morgen"].strftime("%Y-%m-%d")
    dag_naam = WEEKDAGEN[r["weekdag_morgen"]].capitalize()

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
            "id":          "SKU",
            "naam":        "Artikel",
            "eenheid":     "Eenheid",
            "besteladvies":"Bestellen",
        })
        with st.expander(f"**{lev}** — {len(df_lev)} artikel(en)", expanded=True):
            st.dataframe(df_display, hide_index=True, use_container_width=True)

            cfg   = dl.SUPPLIER_CONFIG.get(lev, {})
            email = cfg.get("email", "")

            col_mail, col_csv = st.columns([3, 2])
            with col_mail:
                mailto = dl.genereer_mailto(lev, df_lev, datum)
                label  = f"📧  Mail naar {lev}" + (f" ({email})" if email else "")
                st.link_button(label, mailto, use_container_width=True, type="primary")
            with col_csv:
                csv = df_lev.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"Download {lev}.csv",
                    data=csv,
                    file_name=f"bestelling_{datum}_{lev.replace(' ', '_')}.csv",
                    mime="text/csv",
                    key=f"dl_{lev}",
                    use_container_width=True,
                )

    st.divider()
    alle_df = approved[approved["besteladvies"] > 0][
        ["leverancier", "id", "naam", "eenheid", "besteladvies"]
    ].copy()
    alle_df.columns = ["Leverancier", "SKU", "Artikel", "Eenheid", "Bestellen"]
    st.download_button(
        label="Download complete bestellijst",
        data=alle_df.to_csv(index=False).encode("utf-8"),
        file_name=f"bestelling_{datum}_compleet.csv",
        mime="text/csv",
        use_container_width=True,
        type="primary",
    )

    if st.button("Nieuwe dag starten", use_container_width=True):
        for key in ["closing_data","forecast_result","advies_df","approved_orders"]:
            st.session_state[key] = None
        st.session_state.pagina = "📋  Dag afsluiten"
        st.rerun()

# ── Scherm 5 — Leerrapport ────────────────────────────────────────────────
def page_leerrapport() -> None:
    st.title("📈  Leerrapport")
    st.caption(
        "Elke dag dat je het werkelijke resultaat invult, leert het systeem. "
        "De correctiefactor per weekdag wordt automatisch toegepast op de volgende forecast."
    )

    overzicht = learning.laad_accuracy_overzicht()

    if overzicht is None or overzicht.empty:
        st.info(
            "Nog geen data beschikbaar. Vul dagelijks het werkelijke resultaat in "
            "op het sluitscherm — na 3 dagen per weekdag start de automatische correctie."
        )
        _toon_log_tabel()
        return

    st.subheader("Accuraatheid per weekdag")
    st.dataframe(
        overzicht.style.format({
            "Gem. afwijking %":  "{:+.1f}%",
            "Gem. abs. fout %":  "{:.1f}%",
            "Correctiefactor":   "{:.3f}",
        }).background_gradient(
            subset=["Gem. abs. fout %"], cmap="RdYlGn_r"
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "**Gem. afwijking %** = gemiddelde afwijking (+ = systeem zat te laag, - = te hoog). "
        "**Correctiefactor** = wordt automatisch toegepast op de volgende forecast voor die weekdag. "
        "Correctie is alleen actief na 3+ datapunten."
    )

    # ── Notitie-analyse ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Notities & patronen")
    st.caption(
        "Notities die je op het sluitscherm schrijft worden bijgehouden. "
        "Zodra dezelfde notitie 2+ keer is genoteerd, verschijnt hier de gemiddelde afwijking. "
        "Zo zie je welke omstandigheden (markt, terras, evenement) structureel meer of minder bonnen opleveren."
    )
    notitie_df = learning.laad_notitie_analyse()
    if notitie_df is not None:
        st.dataframe(
            notitie_df.style.format({"Gem. afwijking %": "{:+.1f}%"}),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "Een positieve afwijking % betekent dat het werkelijke aantal bonnen hoger was dan "
            "de forecast — het systeem heeft die situatie onderschat."
        )
    else:
        st.info(
            "Nog geen patronen gevonden. Schrijf elke dag een korte notitie als er iets bijzonders is "
            "(bv. 'markt voor de deur', 'terras dicht regen', 'grote groep geannuleerd'). "
            "Na 2 gelijke notities verschijnt hier de analyse."
        )

    st.divider()
    _toon_log_tabel()


def _toon_log_tabel() -> None:
    st.subheader("Forecast log")
    df = learning._alle_logs()
    if df.empty:
        st.info("Nog geen forecasts gelogd.")
        return

    WEEKDAGNAMEN = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
    df["weekdag_naam"] = df["weekdag"].map(
        lambda d: WEEKDAGNAMEN[int(d)] if pd.notna(d) else ""
    )
    df["datum"] = pd.to_datetime(df["datum"]).dt.strftime("%d/%m/%Y")
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
        "notitie":          "Notitie manager",
    })
    st.dataframe(weergave, hide_index=True, use_container_width=True)

# ── Navigatie ──────────────────────────────────────────────────────────────
def main() -> None:
    init_state()

    if not st.session_state.ingelogd:
        page_login()
        return

    with st.sidebar:
        st.title("🍟  Besteltool")
        st.caption("Family Maarssen — Bisonspoor")
        st.divider()

        pagina = st.radio(
            "Navigatie",
            options=PAGINAS,
            index=PAGINAS.index(st.session_state.pagina),
            label_visibility="collapsed",
        )
        if pagina != st.session_state.pagina:
            st.session_state.pagina = pagina
            st.rerun()

        st.divider()
        st.caption("Voortgang")
        st.write("✅ Dag afgesloten"     if st.session_state.closing_data   else "⬜ Dag afsluiten")
        st.write("✅ Forecast berekend"  if st.session_state.forecast_result else "⬜ Forecast")
        st.write("✅ Bestelling goedgekeurd" if st.session_state.approved_orders is not None else "⬜ Bestelreview")

        st.divider()
        if st.button("Uitloggen", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    scherm = st.session_state.pagina
    if scherm == "📋  Dag afsluiten":
        page_closing()
    elif scherm == "📊  Forecast morgen":
        page_forecast()
    elif scherm == "✅  Bestelreview":
        page_review()
    elif scherm == "📤  Export":
        page_export()
    else:
        page_leerrapport()


main()
