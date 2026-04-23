"""Producten & Leveranciers — overzicht + wizard nieuw product."""
from __future__ import annotations
import pandas as pd
import streamlit as st
import db
from cache import get_products, get_leveranciers_dict, get_leveranciers_lijst

SUPPLIER_TYPE_MAP = {
    "Hanos": "wholesale", "Vers Leverancier": "fresh",
    "Bakkersland": "bakery", "Heineken Distrib.": "beer", "Overig": "other",
}

EENHEID_LABELS = {
    "kg":    ("Gewicht (kg)",   "Zak / doos van"),
    "stuk":  ("Stuks",          "Doos van"),
    "liter": ("Vloeistof (L)",  "Verpakking van"),
}
EENHEID_SUFFIX = {"kg": "kg", "stuk": "stuks", "liter": "L"}

GEBRUIK_OPTIES = {
    "Weinig":    {"buffer_pct": 0.15, "vraag_hint": 0.05,
                  "toelichting": "bijv. speciale sausen, weinig besteld"},
    "Normaal":   {"buffer_pct": 0.20, "vraag_hint": 0.10,
                  "toelichting": "meeste dagelijkse producten"},
    "Veel":      {"buffer_pct": 0.25, "vraag_hint": 0.20,
                  "toelichting": "bijv. friet, brood, drank"},
    "Heel veel": {"buffer_pct": 0.30, "vraag_hint": 0.35,
                  "toelichting": "bijv. water, ketchup — bijna altijd nodig"},
}


def _wizard_reset() -> None:
    for k in list(st.session_state.keys()):
        if k.startswith("wiz_"):
            del st.session_state[k]


def _wizard_nieuw_product(tenant_id: str, df_producten: pd.DataFrame) -> None:
    leveranciers_lijst = get_leveranciers_lijst(tenant_id)
    lev_namen = [l["name"] for l in leveranciers_lijst] if leveranciers_lijst else list(SUPPLIER_TYPE_MAP.keys())

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

        if stap == 1:
            st.markdown("### Hoe heet het product en bij welke leverancier?")
            st.caption("Gebruik de naam zoals hij op de factuur of in het ordersysteem staat.")

            naam = st.text_input("Productnaam", value=st.session_state.wiz_naam,
                                 placeholder="bijv. Friet diepvries 9mm")
            sku = st.text_input(
                "SKU-code (artikelnummer)", value=st.session_state.wiz_sku,
                placeholder="bijv. SKU-031",
                help="De code zoals de leverancier hem gebruikt. Wordt automatisch hoofdletters.",
            )
            lev = st.selectbox(
                "Leverancier", options=lev_namen,
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
                    st.session_state.wiz_naam        = naam.strip()
                    st.session_state.wiz_sku         = sku.strip().upper()
                    st.session_state.wiz_leverancier = lev
                    st.session_state.wiz_stap        = 2
                    st.session_state.wiz_open        = True
                    st.rerun()

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

        elif stap == 3:
            eenheid = st.session_state.wiz_eenheid
            prefix  = EENHEID_LABELS[eenheid][1]
            suffix  = EENHEID_SUFFIX[eenheid]

            st.markdown("### Hoe groot is één verpakking?")
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
                    st.session_state.wiz_pack_qty  = pack_qty
                    st.session_state.wiz_min_stock = pack_qty
                    st.session_state.wiz_stap      = 4
                    st.session_state.wiz_open      = True
                    st.rerun()
            with col_t:
                st.button("← Terug", key="wiz_terug_3", on_click=lambda: st.session_state.update({"wiz_stap": 2}))

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

        elif stap == 5:
            eenheid = st.session_state.wiz_eenheid
            suffix  = EENHEID_SUFFIX[eenheid]

            st.markdown("### Bijna klaar — controleer de instellingen")
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

        elif stap == 6:
            eenheid  = st.session_state.wiz_eenheid
            suffix   = EENHEID_SUFFIX[eenheid]
            lev_naam = st.session_state.wiz_leverancier

            st.markdown("### Klopt alles? Dan slaan we het op.")

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
                    lev_lijst    = get_leveranciers_lijst(tenant_id)
                    supplier_id  = next(
                        (l["id"] for l in lev_lijst if l["name"] == lev_naam), None
                    )

                    ok, fout = db.sla_product_op(
                        tenant_id          = tenant_id,
                        sku_id             = st.session_state.wiz_sku,
                        naam               = st.session_state.wiz_naam,
                        eenheid            = eenheid,
                        verpakkingseenheid = float(st.session_state.wiz_pack_qty),
                        vraag_per_cover    = round(float(st.session_state.wiz_vraag), 4),
                        minimumvoorraad    = float(st.session_state.wiz_min_stock),
                        buffer_pct         = round(st.session_state.wiz_buffer_pct / 100, 2),
                        supplier_id        = supplier_id,
                    )

                    if ok:
                        opgeslagen_naam = st.session_state.wiz_naam
                        opgeslagen_sku  = st.session_state.wiz_sku
                        get_products.clear()
                        _wizard_reset()
                        st.success(
                            f"Product **{opgeslagen_naam}** ({opgeslagen_sku}) "
                            f"opgeslagen onder **{lev_naam}**."
                        )
                        st.rerun()
                    else:
                        st.error(f"Opslaan mislukt: {fout}")

            with col_t:
                st.button("← Terug", key="wiz_terug_6", on_click=lambda: st.session_state.update({"wiz_stap": 5}))


def render() -> None:
    tenant_id  = st.session_state.tenant_id
    lev_config = get_leveranciers_dict(tenant_id)

    st.title("Producten & Leveranciers")
    st.caption(
        "Volledig overzicht van alle artikelen per leverancier. "
        "E-mailadressen zijn instelbaar via Beheer → Leveranciers."
    )

    df = get_products(tenant_id)

    LEVERANCIERS_VOLGORDE = ["Hanos", "Vers Leverancier", "Bakkersland", "Heineken Distrib.", "Overig"]
    alle_leveranciers = [l for l in LEVERANCIERS_VOLGORDE if l in df["leverancier"].values]

    totaal_col1, totaal_col2, totaal_col3 = st.columns(3)
    totaal_col1.metric("Totaal artikelen",  len(df))
    totaal_col2.metric("Leveranciers",      df["leverancier"].nunique())
    totaal_col3.metric("Te bestellen SKUs", len(df[df["minimumvoorraad"] > 0]))

    st.divider()

    for lev in alle_leveranciers:
        df_lev = df[df["leverancier"] == lev].copy()
        cfg    = lev_config.get(lev, {})
        email  = cfg.get("email", "")
        n      = len(df_lev)

        email_badge = f" · {email}" if email else " · **geen e-mail ingesteld**"
        with st.expander(f"**{lev}** — {n} artikel(en){email_badge}", expanded=True):
            weergave = df_lev[[
                "id", "naam", "eenheid", "verpakkingseenheid",
                "vraag_per_cover", "buffer_pct", "minimumvoorraad",
            ]].rename(columns={
                "id":                "SKU",
                "naam":              "Artikel",
                "eenheid":           "Eenheid",
                "verpakkingseenheid":"Verpakking",
                "vraag_per_cover":   "Vraag/bon",
                "buffer_pct":        "Buffer %",
                "minimumvoorraad":   "Min. voorraad",
            }).copy()
            weergave["Buffer %"] = (weergave["Buffer %"] * 100).round(0).astype(int).astype(str) + "%"
            st.dataframe(weergave, hide_index=True, use_container_width=True)

            if not email:
                st.warning(
                    f"Geen e-mailadres ingesteld voor **{lev}**. "
                    "Stel dit in via Beheer → Leveranciers zodat bestellingen automatisch verstuurd kunnen worden."
                )

    st.divider()
    _wizard_nieuw_product(tenant_id, df)
