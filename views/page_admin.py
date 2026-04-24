"""Admin — cross-tenant beheer (klanten, gebruikers, leveranciers)."""
from __future__ import annotations
import streamlit as st
import db
import monitoring
import email_service as mail


def render() -> None:
    if st.session_state.get("user_rol") != "super_admin":
        st.error("Geen toegang. Deze pagina is alleen voor super administrators.")
        st.stop()

    st.title("Beheer")
    st.caption("Klanten, gebruikers en leveranciersinstellingen beheren.")
    tab_klanten, tab_onboarding, tab_gebruikers, tab_systeem = st.tabs(
        ["Klanten", "Nieuwe klant", "Gebruikers", "Systeem"]
    )

    with tab_klanten:
        _tab_klanten()

    with tab_onboarding:
        _tab_nieuwe_klant()

    with tab_gebruikers:
        _tab_gebruikers()

    with tab_systeem:
        _tab_systeem()


def _tab_nieuwe_klant() -> None:
    st.subheader("Nieuwe klant onboarden")
    st.caption(
        "Maak een nieuwe tenant aan met één admin-gebruiker. "
        "Er wordt automatisch een welkomstmail verstuurd."
    )

    with st.form("form_onboarding"):
        st.markdown("**Restaurantgegevens**")
        col1, col2 = st.columns(2)
        with col1:
            naam = st.text_input("Naam restaurant", placeholder="Restaurant De Bijenkorf")
        with col2:
            slug = st.text_input(
                "Slug",
                placeholder="de-bijenkorf",
                help="Alleen a-z, 0-9 en koppeltekens. Wordt gebruikt op het inlogscherm.",
            )

        st.markdown("**Admin-gebruiker**")
        col3, col4 = st.columns(2)
        with col3:
            admin_username  = st.text_input("Gebruikersnaam admin")
            admin_email     = st.text_input("E-mailadres admin", placeholder="manager@restaurant.nl")
        with col4:
            admin_wachtwoord = st.text_input("Tijdelijk wachtwoord", type="password",
                                              help="De admin kan dit later zelf resetten.")

        aanmaken = st.form_submit_button(
            "Klant aanmaken + welkomstmail sturen", type="primary", use_container_width=True
        )

    if aanmaken:
        if not naam or not slug or not admin_username or not admin_wachtwoord or not admin_email:
            st.error("Vul alle velden in.")
        elif " " in slug or slug != slug.lower():
            st.error("Slug mag geen spaties bevatten en moet kleine letters zijn.")
        else:
            tenant_id = db.maak_tenant_met_admin(
                naam.strip(), slug.strip().lower(),
                admin_username.strip(), admin_wachtwoord, admin_email.strip(),
            )
            if tenant_id:
                ok_mail, fout_mail = mail.verzend_welkomstmail(
                    to_email=admin_email.strip(),
                    gebruikersnaam=admin_username.strip(),
                    restaurant_naam=naam.strip(),
                    tenant_slug=slug.strip().lower(),
                )
                if ok_mail:
                    st.success(
                        f"✅ Klant **{naam}** aangemaakt. "
                        f"Welkomstmail verstuurd naar {admin_email}."
                    )
                else:
                    st.success(f"✅ Klant **{naam}** aangemaakt.")
                    st.warning(f"Welkomstmail kon niet worden verstuurd: {fout_mail}")
            else:
                st.error("Aanmaken mislukt — slug bestaat mogelijk al.")


def _tab_systeem() -> None:
    st.subheader("Systeem verificatie")
    st.caption("Controleer of externe integraties correct werken.")

    st.markdown("**Sentry — error tracking**")
    st.write(
        "Stuur een test-exception naar Sentry om te bevestigen dat errors "
        "worden ontvangen met de juiste tenant/user/pagina tags."
    )
    if st.button("Verstuur Sentry test-exception", type="primary"):
        try:
            monitoring.veroorzaak_test_exception()
        except RuntimeError:
            st.success(
                "Test-exception verstuurd naar Sentry. "
                "Controleer het Sentry dashboard — je ziet een RuntimeError met "
                "tenant_id en pagina tags."
            )

    st.divider()
    st.markdown("**Verzendhistorie — sent_emails tabel**")
    tenant_id = st.session_state.get("tenant_id")
    emails = db.laad_verzonden_emails(tenant_id, limit=10) if tenant_id else []
    if emails:
        import pandas as pd
        st.dataframe(pd.DataFrame(emails), hide_index=True, use_container_width=True)
    else:
        st.info("Nog geen verzonden bestellingen gevonden in sent_emails.")


def _tab_klanten() -> None:
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


def _tab_gebruikers() -> None:
    st.subheader("Bestaande gebruikers")
    gebruikers         = db.laad_alle_gebruikers()
    ingelogd_username  = st.session_state.get("user_naam", "")
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
                    nieuw_email      = st.text_input(
                        "E-mailadres", value=g.get("email") or "",
                        placeholder="voor wachtwoord reset",
                    )
                with col2:
                    nieuw_wachtwoord = st.text_input(
                        "Nieuw wachtwoord", type="password",
                        placeholder="Laat leeg om niet te wijzigen",
                    )
                    nieuwe_rol = st.selectbox(
                        "Rol", ["manager", "admin"],
                        index=0 if g["role"] == "manager" else 1,
                    )
                if st.form_submit_button("Opslaan", type="primary"):
                    if not nieuwe_username.strip():
                        st.error("Gebruikersnaam mag niet leeg zijn.")
                    else:
                        ok, fout = db.update_gebruiker(
                            g["tenant_id"], g["id"], nieuwe_username.strip(),
                            nieuwe_naam.strip(), nieuwe_rol,
                            nieuw_wachtwoord or None,
                            email=nieuw_email.strip() or None,
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
                            ok, fout = db.verwijder_gebruiker(g["tenant_id"], g["id"])
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
                gebruiker_email = st.text_input(
                    "E-mailadres", placeholder="voor wachtwoord reset (optioneel)"
                )
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
                    tenant_id_new = tenant_opties[gekozen_tenant]
                    gelukt = db.maak_gebruiker_aan(
                        tenant_id_new, gebruikersnaam.strip(), wachtwoord,
                        rol, volledige_naam.strip(),
                        email=gebruiker_email.strip() or None,
                    )
                    if gelukt:
                        st.success(f"Gebruiker **{gebruikersnaam}** aangemaakt voor {gekozen_tenant}.")
                    else:
                        st.error("Aanmaken mislukt — gebruikersnaam bestaat mogelijk al.")
