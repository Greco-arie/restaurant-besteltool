"""Wachtwoord reset — stap 1 (aanvraag) en stap 3 (nieuw wachtwoord via token-URL)."""
from __future__ import annotations
import os
import streamlit as st
import db
import email_service as mail


def render_aanvraag() -> None:
    """Stap 1: gebruiker vraagt een reset-link aan via tenant_slug + e-mail."""
    col_l, col_m, col_r = st.columns([1, 1.4, 1])
    with col_m:
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Wachtwoord vergeten?")
        st.caption(
            "Vul je restaurant en e-mailadres in. "
            "Als het adres bekend is, ontvang je een link om je wachtwoord in te stellen."
        )
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("reset_aanvraag_form"):
            tenant_slug = st.text_input(
                "Restaurant",
                placeholder="jouw-restaurant",
                help="De slug die je ook gebruikt op het inlogscherm.",
            )
            email = st.text_input("E-mailadres")
            verzenden = st.form_submit_button(
                "Stuur reset-link", type="primary", use_container_width=True
            )

        if verzenden:
            if not tenant_slug.strip() or not email.strip():
                st.error("Vul restaurant en e-mailadres in.")
                return

            gebruiker = db.zoek_gebruiker_op_email(tenant_slug.strip(), email.strip())
            if gebruiker:
                token = db.maak_reset_token(gebruiker["tenant_id"], gebruiker["user_id"])
                if token:
                    basis = _basis_url()
                    reset_url = f"{basis}?token={token}" if basis else None
                    mail.verzend_reset_mail(
                        to_email=email.strip(),
                        token=token,
                        restaurant_naam=tenant_slug.strip(),
                        gebruikersnaam=gebruiker["username"],
                        reset_url=reset_url,
                    )

            # Altijd hetzelfde bericht — anti-enumeration
            st.success(
                "Als dit e-mailadres bij ons bekend is, ontvang je een e-mail "
                "met een reset-link. Controleer ook je spamfolder."
            )


def render_nieuw_wachtwoord(token: str) -> None:
    """Stap 3: gebruiker stelt nieuw wachtwoord in via token uit URL."""
    col_l, col_m, col_r = st.columns([1, 1.4, 1])
    with col_m:
        st.markdown("<br>", unsafe_allow_html=True)

        gebruiker_info = db.verifieer_reset_token(token)
        if not gebruiker_info:
            st.error(
                "Deze reset-link is verlopen of al gebruikt. "
                "Vraag een nieuwe link aan via het inlogscherm."
            )
            if st.button("Terug naar inloggen", use_container_width=True):
                st.query_params.clear()
                st.rerun()
            return

        st.subheader("Nieuw wachtwoord instellen")
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("reset_nieuw_wachtwoord_form"):
            nieuw = st.text_input("Nieuw wachtwoord", type="password")
            bevestig = st.text_input("Bevestig nieuw wachtwoord", type="password")
            opslaan = st.form_submit_button(
                "Wachtwoord opslaan", type="primary", use_container_width=True
            )

        if opslaan:
            if not nieuw:
                st.error("Vul een nieuw wachtwoord in.")
                return
            if nieuw != bevestig:
                st.error("Wachtwoorden komen niet overeen.")
                return
            if len(nieuw) < 8:
                st.error("Wachtwoord moet minimaal 8 tekens lang zijn.")
                return

            # Foutmelding bewust niet getoond (anti-enumeration \u2014 pre-auth flow).
            ok, _fout = db.reset_wachtwoord(
                gebruiker_info["tenant_id"],
                gebruiker_info["user_id"],
                nieuw,
            )
            if ok:
                db.invalideer_token(token)
                st.session_state["_reset_success"] = True
                st.query_params.clear()
                st.rerun()
            else:
                st.error("Opslaan mislukt. Probeer opnieuw of vraag een nieuwe link aan.")


def _basis_url() -> str:
    """Lees de basis-URL van de app uit secrets of omgevingsvariabelen."""
    try:
        return st.secrets.get("app", {}).get("base_url", "").rstrip("/")
    except Exception:
        pass
    return os.getenv("APP_BASE_URL", "").rstrip("/")
