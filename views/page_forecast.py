"""Forecast morgen — samenvatting van berekend besteladvies."""
from __future__ import annotations
from datetime import timedelta
import streamlit as st
import recommendation as rc
from cache import get_leveranciers_dict, toon_voltooid_overlay

PAGE_CLOSING  = "Dag afsluiten"
PAGE_REVIEW   = "Bestelreview"
WEEKDAGEN     = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
CONFIDENCE_LABEL = {"hoog": "Hoog", "gemiddeld": "Gemiddeld", "laag": "Laag"}


def render() -> None:
    if st.session_state.approved_orders is not None:
        toon_voltooid_overlay("forecast")

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

    tenant_id         = st.session_state.tenant_id
    leveranciers_data = get_leveranciers_dict(tenant_id)
    if leveranciers_data:
        datum_vandaag_fc = r["datum_morgen"] - timedelta(days=1)
        st.divider()
        st.subheader("Volgende leveringen")
        lev_cols = st.columns(len(leveranciers_data))
        for idx, (lev_naam, lev_data) in enumerate(sorted(leveranciers_data.items())):
            info     = rc.volgende_leverdag_info(lev_naam, datum_vandaag_fc, leveranciers_data)
            dag_nl   = info["weekdag_naam"].capitalize()
            datum_nl = info["datum"].strftime("%d %b")
            delta    = f"over {info['dagen']} dag{'en' if info['dagen'] != 1 else ''}"
            with lev_cols[idx]:
                st.metric(f"**{lev_naam}**", f"{dag_nl} {datum_nl}", delta=delta)
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
