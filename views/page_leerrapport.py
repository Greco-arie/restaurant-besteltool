"""Leerrapport — forecast accuracy per weekdag + notitie-analyse + forecast log."""
from __future__ import annotations
import pandas as pd
import streamlit as st
import learning


def render() -> None:
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
