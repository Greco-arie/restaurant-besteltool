"""Export — bestellijst per leverancier mailen of downloaden."""
from __future__ import annotations
import streamlit as st
import recommendation as rc
import email_service as mail
import monitoring
import db
from cache import get_leveranciers_dict

PAGE_REVIEW   = "Bestelreview"
PAGE_CLOSING  = "Dag afsluiten"
WEEKDAGEN     = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def render() -> None:
    tenant_id = st.session_state.tenant_id

    st.title("Export")
    st.caption("Bestellijst per leverancier")

    if st.session_state.approved_orders is None:
        st.warning("Keur eerst het besteladvies goed.")
        if st.button("Naar bestelreview"):
            st.session_state.pagina = PAGE_REVIEW
            st.rerun()
        return

    r          = st.session_state.forecast_result
    approved   = st.session_state.approved_orders
    lev_config = get_leveranciers_dict(tenant_id)
    datum      = r["datum_morgen"].strftime("%Y-%m-%d")
    dag_naam   = WEEKDAGEN[r["weekdag_morgen"]].capitalize()

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

            col_mail, col_csv = st.columns([3, 2])
            with col_mail:
                cfg_lev   = lev_config.get(lev, {})
                lev_email = cfg_lev.get("email", "")
                if not lev_email:
                    st.warning(f"Geen e-mailadres voor {lev} — stel in via Beheer → Leveranciers")
                else:
                    send_key = f"send_{lev}"
                    if st.button(
                        f"\U0001f4e7 Mail naar {lev} ({lev_email})",
                        key=send_key,
                        use_container_width=True,
                    ):
                        manager_email = st.session_state.get("user_email") or None
                        tenant_slug   = st.session_state.get("tenant_slug", "restaurant")
                        with st.spinner(f"E-mail versturen naar {lev}..."):
                            ok, resultaat = mail.verzend_bestelling(
                                leverancier   = lev,
                                df_lev        = df_lev,
                                bestel_datum  = datum,
                                lev_config    = cfg_lev,
                                tenant_slug   = tenant_slug,
                                manager_email = manager_email,
                            )
                        if ok:
                            st.success(f"Bestelling verzonden naar {lev_email} (id: {resultaat})")
                            monitoring.log_event(
                                "bestelling_verzonden",
                                leverancier=lev,
                                to=lev_email,
                                datum=datum,
                            )
                            db.sla_verzonden_email_op(
                                tenant_id     = tenant_id,
                                supplier_naam = lev,
                                bestel_datum  = datum,
                                resend_id     = resultaat,
                                supplier_id   = cfg_lev.get("id"),
                            )
                        else:
                            st.error(f"Verzenden mislukt: {resultaat}")
                            monitoring.log_error(
                                "bestelling_verzend_fout",
                                fout=resultaat,
                                leverancier=lev,
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
