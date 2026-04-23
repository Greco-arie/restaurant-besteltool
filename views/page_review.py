"""Bestelreview — goedkeuren of aanpassen van besteladvies."""
from __future__ import annotations
import streamlit as st
import inventory as inv
from cache import heeft_recht, toon_voltooid_overlay

PAGE_CLOSING = "Dag afsluiten"
PAGE_FORECAST = "Forecast"
PAGE_EXPORT   = "Export"


def render() -> None:
    if st.session_state.approved_orders is not None:
        toon_voltooid_overlay("review")

    st.title("Bestelreview")

    if st.session_state.advies_df is None:
        st.warning("Bereken eerst de forecast.")
        if st.button("Naar dag afsluiten"):
            st.session_state.pagina = PAGE_CLOSING
            st.rerun()
        return

    tenant_id = st.session_state.tenant_id
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

    signalen = inv.laad_verspilling_signalen(tenant_id)
    if signalen:
        sku_naar_naam = dict(zip(advies_df["id"], advies_df["naam"]))
        buffer_map    = dict(zip(advies_df["id"], advies_df["buffer_pct"]))

        with st.container():
            st.markdown("**Attentiepunten uit de voorraadhistorie (30 dagen)**")
            for sku, counts in signalen.items():
                naam          = sku_naar_naam.get(sku, sku)
                buffer_huidig = int(round(buffer_map.get(sku, 0) * 100))
                if counts["marge_te_hoog"] >= 3:
                    n = counts["marge_te_hoog"]
                    buffer_voorstel = max(5, buffer_huidig - 5)
                    st.warning(
                        f"**{naam}** — {n}× verlopen of weggegooid in 30 dagen. "
                        f"Huidige marge: {buffer_huidig}%. Overweeg te verlagen naar {buffer_voorstel}%."
                    )
                if counts["marge_te_laag"] >= 3:
                    n = counts["marge_te_laag"]
                    buffer_voorstel = buffer_huidig + 5
                    st.error(
                        f"**{naam}** — {n}× sneller op dan verwacht in 30 dagen. "
                        f"Huidige marge: {buffer_huidig}%. Bestel vaker of verhoog naar {buffer_voorstel}%."
                    )
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

    kan_goedkeuren = heeft_recht("bestellingen_plaatsen")
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
