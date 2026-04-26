"""Gedeelde Streamlit-widgets voor admin-pagina's.

Hier leven view-helpers die door meerdere ``views/page_*.py`` modules
worden gebruikt. Reden voor een eigen module: een directe
``from views.page_instellingen import …`` in ``views/page_admin.py``
creëert verborgen koppeling tussen pagina's. Een neutrale
widget-laag voorkomt dat één view stilletjes breekt als de andere
een import-fout heeft.
"""
from __future__ import annotations

import streamlit as st

import state
from auth_helpers import lees_basis_url, trigger_admin_password_reset


def render_reset_knop(g: dict, key_prefix: str) -> None:
    """Render een 'Stuur reset-link' knop met confirm-dialog en e-mail-guard.

    Parameters
    ----------
    g          : gebruiker-rij uit ``db.laad_tenant_gebruikers`` of
                 ``db.laad_alle_gebruikers``. Vereist: ``id``, ``username``,
                 ``tenant_id``, ``email``.
    key_prefix : prefix voor ``st.session_state``-keys. MOET uniek zijn per
                 page-context (bijv. ``"inst"`` voor Instellingen, ``"adm"``
                 voor Beheer) zodat dezelfde gebruiker in twee tabs een
                 onafhankelijke confirm-state houdt.
    """
    target_email = (g.get("email") or "").strip()
    if not target_email:
        st.button(
            "Stuur reset-link",
            key      = f"reset_{key_prefix}_{g['id']}_noemail",
            disabled = True,
            help     = "Geen e-mailadres bekend — vul eerst een e-mail in.",
        )
        return

    confirm_key = f"confirm_reset_{key_prefix}_{g['id']}"
    if st.session_state.get(confirm_key):
        st.info(
            f"Stuur een reset-link naar **{target_email}**? "
            "De medewerker kiest dan zelf een nieuw wachtwoord."
        )
        col_ja, col_nee = st.columns(2)
        with col_ja:
            if st.button(
                "Ja, verstuur",
                key  = f"reset_ja_{key_prefix}_{g['id']}",
                type = "primary",
            ):
                actor    = state.require_user()
                basis    = lees_basis_url()
                ok, info = trigger_admin_password_reset(
                    actor     = actor,
                    target    = g,
                    basis_url = basis,
                )
                st.session_state.pop(confirm_key, None)
                if ok:
                    st.success(f"Reset-link verstuurd naar {target_email}.")
                elif info == "geen_basis_url":
                    st.error(
                        "App-basis-URL ontbreekt — configureer "
                        "`app.base_url` in secrets of `APP_BASE_URL` env."
                    )
                elif info == "token_mint_failed":
                    st.error("Token aanmaken mislukt — probeer opnieuw.")
                elif info == "cross_tenant_forbidden":
                    st.error("Je mag geen gebruiker uit een andere tenant resetten.")
                else:
                    st.error(f"Versturen mislukt: {info}")
                st.rerun()
        with col_nee:
            if st.button("Annuleren", key=f"reset_nee_{key_prefix}_{g['id']}"):
                st.session_state.pop(confirm_key, None)
                st.rerun()
    else:
        if st.button(
            "Stuur reset-link",
            key  = f"reset_{key_prefix}_{g['id']}",
            help = f"Stuurt een wachtwoord-reset-link naar {target_email}.",
        ):
            st.session_state[confirm_key] = True
            st.rerun()
