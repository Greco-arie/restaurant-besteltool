"""Inventaris — huidige voorraad bekijken + handmatig corrigeren + verbruikspatronen."""
from __future__ import annotations
import pandas as pd
import streamlit as st
import inventory as inv
from cache import get_products, heeft_recht


def render() -> None:
    tenant_id = st.session_state.tenant_id
    user_naam = st.session_state.user_naam

    st.title("Inventaris")
    st.caption(
        "Bekijk de huidige voorraad en corrigeer waar nodig. "
        "Elke correctie wordt opgeslagen en gebruikt om het systeem te verbeteren."
    )

    df_producten = get_products(tenant_id)
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

    if not heeft_recht("voorraad_tellen"):
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
                "Verspilling — verlopen / over datum",
                "Verspilling — beschadigd / gemorst",
                "Intern gebruik — personeelsmaaltijd",
                "Intern gebruik — proefgerecht / tasting",
                "Portionering — groter dan recept",
                "Sneller op dan verwacht",
                "Telling gecorrigeerd — was te hoog",
                "Levering ingeboekt — was vergeten",
                "Retour van klant",
                "Telling gecorrigeerd — was te laag",
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
