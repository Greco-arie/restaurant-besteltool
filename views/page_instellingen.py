"""Instellingen — leveranciersbeheer + gebruikersbeheer voor de eigen tenant."""
from __future__ import annotations
import streamlit as st
import db
import permissions as perm
from cache import get_leveranciers_lijst


def render() -> None:
    tenant_id = st.session_state.tenant_id

    if st.session_state.user_rol not in ("admin", "manager"):
        st.error("Geen toegang.")
        return

    st.title("Instellingen")
    st.caption(
        "Beheer de leveranciers en medewerkers van jouw restaurant. "
        "Stel leverdagen en e-mailadressen in per leverancier."
    )

    tab_lev, tab_gebr = st.tabs(["Leveranciers", "Gebruikers"])

    with tab_lev:
        _tab_leveranciers(tenant_id)

    with tab_gebr:
        _tab_gebruikers(tenant_id)


def _tab_leveranciers(tenant_id: str) -> None:
    st.subheader("Leveranciers & leveringsschema")
    st.caption(
        "Vink aan op welke dag elke leverancier levert. "
        "De besteltool gebruikt dit om automatisch voor het juiste aantal dagen te bestellen."
    )

    leveranciers = get_leveranciers_lijst(tenant_id)
    DAGLETTERS   = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
    DAG_KOLOMMEN = ["levert_ma", "levert_di", "levert_wo", "levert_do",
                    "levert_vr", "levert_za", "levert_zo"]

    if not leveranciers:
        st.info("Nog geen leveranciers. Voeg ze toe via het formulier hieronder.")
    else:
        for lev in leveranciers:
            leverdagen_str = " · ".join(
                DAGLETTERS[i]
                for i, k in enumerate(DAG_KOLOMMEN)
                if lev.get(k, False)
            ) or "geen leverdagen"
            email_badge = lev.get("email") or "geen e-mail"

            with st.expander(
                f"**{lev['name']}** — {leverdagen_str} — {email_badge}",
                expanded=False,
            ):
                with st.form(f"form_lev_edit_{lev['id']}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        naam_in   = st.text_input("Naam leverancier", value=lev["name"])
                        email_in  = st.text_input("E-mailadres", value=lev.get("email", ""),
                                                  placeholder="inkoop@leverancier.nl")
                        aanhef_in = st.text_input("Aanhef in e-mail", value=lev.get("aanhef", "Beste leverancier,"))
                    with c2:
                        lt_in = st.number_input(
                            "Levertijd (dagen)",
                            min_value=1, max_value=14,
                            value=int(lev.get("lead_time_days", 1)),
                            help="Hoeveel dagen duurt het van bestelling tot levering?",
                        )

                    st.markdown("**Leverdagen** — vink aan op welke dagen deze leverancier levert:")
                    dag_cols = st.columns(7)
                    levert_waarden = []
                    for i, (dagletter, dagkolom) in enumerate(zip(DAGLETTERS, DAG_KOLOMMEN)):
                        levert_waarden.append(
                            dag_cols[i].checkbox(dagletter, value=bool(lev.get(dagkolom, False)),
                                                 key=f"lev_{lev['id']}_{dagkolom}")
                        )

                    col_save, col_del = st.columns([3, 1])
                    with col_save:
                        opslaan = st.form_submit_button("Opslaan", type="primary", use_container_width=True)
                    with col_del:
                        verwijder = st.form_submit_button("Verwijder", use_container_width=True)

                if opslaan:
                    ok, fout = db.update_leverancier(
                        tenant_id, lev["id"], naam_in, email_in, aanhef_in, lt_in,
                        *levert_waarden
                    )
                    if ok:
                        st.success(f"**{naam_in}** opgeslagen.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Opslaan mislukt: {fout}")

                if verwijder:
                    ok, fout = db.verwijder_leverancier(tenant_id, lev["id"])
                    if ok:
                        st.success(f"**{lev['name']}** verwijderd.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Verwijderen mislukt: {fout}")

    st.divider()
    with st.expander("➕ Nieuwe leverancier toevoegen", expanded=not leveranciers):
        with st.form("form_nieuwe_leverancier", clear_on_submit=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                nieuw_naam   = st.text_input("Naam leverancier *", placeholder="bijv. Sligro")
                nieuw_email  = st.text_input("E-mailadres", placeholder="inkoop@sligro.nl")
                nieuw_aanhef = st.text_input("Aanhef", value="Beste leverancier,")
            with c2:
                nieuw_lt = st.number_input("Levertijd (dagen)", min_value=1, max_value=14, value=1)

            st.markdown("**Leverdagen:**")
            nd_cols = st.columns(7)
            DAGLETTERS2 = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
            nieuwe_dagen = [
                nd_cols[i].checkbox(DAGLETTERS2[i], key=f"nieuw_dag_{i}")
                for i in range(7)
            ]

            if st.form_submit_button("Leverancier aanmaken", type="primary"):
                if not nieuw_naam.strip():
                    st.error("Naam is verplicht.")
                elif not any(nieuwe_dagen):
                    st.error("Selecteer minimaal 1 leverdag.")
                else:
                    ok, fout = db.maak_leverancier_aan(
                        tenant_id, nieuw_naam, nieuw_email, nieuw_aanhef, nieuw_lt,
                        *nieuwe_dagen
                    )
                    if ok:
                        st.success(f"Leverancier **{nieuw_naam}** aangemaakt.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Aanmaken mislukt: {fout}")

    st.divider()
    st.caption(
        "**Hoe werkt de e-mailknop?**  \n"
        "Op de exportpagina verstuurt de knop 'Mail naar [leverancier]' de bestelling "
        "direct via Resend naar het e-mailadres dat hierboven per leverancier is ingesteld."
    )


def _tab_gebruikers(tenant_id: str) -> None:
    mijn_rol       = st.session_state.user_rol
    mijn_perms     = st.session_state.get("user_permissions", {})
    ingelogde_user = st.session_state.get("user_naam", "")

    heeft_app_recht = any(mijn_perms.get(r) for r in perm.APP_MANAGEMENT_RECHTEN)
    if mijn_rol == "manager" and not heeft_app_recht:
        st.info("Je hebt geen rechten voor gebruikersbeheer. Vraag de admin.")
        return

    st.subheader("Medewerkers")
    st.caption("Beheer rollen en rechten per medewerker. Wat iemand mag hangt af van zijn rol én de checkboxen.")

    alle_gebruikers   = db.laad_alle_gebruikers()
    tenant_gebruikers = [g for g in alle_gebruikers if g["tenant_id"] == tenant_id]
    zichtbaar         = [g for g in tenant_gebruikers
                         if perm.kan_gebruiker_zien(mijn_rol, g["role"])]

    if not zichtbaar:
        st.info("Geen medewerkers om te beheren.")
    else:
        for g in zichtbaar:
            label = f"**{g['username']}** · {g.get('full_name', '')} · {perm.rol_label(g['role'])}"
            with st.expander(label):
                with st.form(f"form_gebr_edit_{g['id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        nieuwe_uname = st.text_input("Gebruikersnaam", value=g["username"])
                        nieuwe_fnaam = st.text_input("Volledige naam", value=g.get("full_name", ""))
                    with c2:
                        nieuw_pw = st.text_input("Nieuw wachtwoord", type="password",
                                                 placeholder="Laat leeg om niet te wijzigen")
                        rol_opties = perm.beschikbare_rollen(mijn_rol)
                        if mijn_rol == "manager" and not mijn_perms.get("rollen_toewijzen"):
                            rol_opties = [g["role"]]
                        rol_idx   = rol_opties.index(g["role"]) if g["role"] in rol_opties else 0
                        nieuwe_rol = st.selectbox(
                            "Rol", rol_opties,
                            format_func=perm.rol_label,
                            index=rol_idx,
                        )

                    nieuwe_rechten: dict | None = None
                    if g["role"] in ("user", "manager"):
                        huidige_rechten = g.get("permissions") or {}
                        te_tonen = (
                            {"App management": perm.RECHTEN_CATEGORIEËN["App management"]}
                            if g["role"] == "manager"
                            else perm.RECHTEN_CATEGORIEËN
                        )
                        nieuwe_rechten = {}
                        for cat_naam, cat_rechten in te_tonen.items():
                            kan_bewerken = perm.kan_rechten_categorie_bewerken(mijn_rol, cat_naam)
                            st.markdown(f"**{cat_naam}**")
                            cols = st.columns(2)
                            for pi, (rk, rl) in enumerate(cat_rechten.items()):
                                nieuwe_rechten[rk] = cols[pi % 2].checkbox(
                                    rl,
                                    value=bool(huidige_rechten.get(rk, False)),
                                    key=f"perm_{g['id']}_{rk}",
                                    disabled=not kan_bewerken,
                                )

                    if st.form_submit_button("Opslaan", type="primary"):
                        if not nieuwe_uname.strip():
                            st.error("Gebruikersnaam mag niet leeg zijn.")
                        elif not perm.kan_rol_wijzigen(mijn_rol, g["role"], nieuwe_rol):
                            st.error("Je mag deze rolwijziging niet uitvoeren.")
                        else:
                            ok, fout = db.update_gebruiker(
                                g["id"], nieuwe_uname.strip(),
                                nieuwe_fnaam.strip(), nieuwe_rol,
                                nieuw_pw or None,
                            )
                            if ok and nieuwe_rechten is not None:
                                db.update_gebruiker_rechten(g["id"], nieuwe_rechten)
                            if ok:
                                st.success("Gegevens bijgewerkt.")
                                st.rerun()
                            else:
                                st.error(f"Opslaan mislukt: {fout}")

                if g["username"] != ingelogde_user:
                    confirm_key = f"confirm_del_gebr_{g['id']}"
                    if st.session_state.get(confirm_key):
                        st.warning(f"Verwijder **{g['username']}**?")
                        col_ja, col_nee = st.columns(2)
                        with col_ja:
                            if st.button("Ja, verwijder", key=f"ja_g_{g['id']}", type="primary"):
                                ok, _ = db.verwijder_gebruiker(g["id"])
                                if ok:
                                    st.session_state.pop(confirm_key, None)
                                    st.success(f"{g['username']} verwijderd.")
                                    st.rerun()
                        with col_nee:
                            if st.button("Annuleren", key=f"nee_g_{g['id']}"):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                    else:
                        if st.button("Verwijder medewerker", key=f"del_g_{g['id']}"):
                            st.session_state[confirm_key] = True
                            st.rerun()

    kan_aanmaken = (
        mijn_rol in ("admin", "super_admin") or
        mijn_perms.get("gebruikers_aanmaken", False)
    )
    if kan_aanmaken:
        st.divider()
        st.subheader("Nieuwe medewerker toevoegen")
        with st.form("form_nieuw_gebr_inst", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nw_uname = st.text_input("Gebruikersnaam *")
                nw_fnaam = st.text_input("Volledige naam")
            with c2:
                nw_pw  = st.text_input("Wachtwoord *", type="password")
                nw_rol_opties = perm.beschikbare_rollen(mijn_rol)
                nw_rol = st.selectbox("Rol", nw_rol_opties, format_func=perm.rol_label)

            nw_rechten: dict = {}
            if nw_rol == "user":
                for cat_naam, cat_rechten in perm.RECHTEN_CATEGORIEËN.items():
                    kan_bewerken = perm.kan_rechten_categorie_bewerken(mijn_rol, cat_naam)
                    st.markdown(f"**{cat_naam}**")
                    cols = st.columns(2)
                    for pi, (rk, rl) in enumerate(cat_rechten.items()):
                        nw_rechten[rk] = cols[pi % 2].checkbox(
                            rl, value=False,
                            key=f"nw_perm_{rk}",
                            disabled=not kan_bewerken,
                        )

            if st.form_submit_button("Medewerker aanmaken", type="primary"):
                if not nw_uname.strip() or not nw_pw:
                    st.error("Gebruikersnaam en wachtwoord zijn verplicht.")
                else:
                    rechten = nw_rechten if nw_rol == "user" else {}
                    gelukt = db.maak_gebruiker_aan(
                        tenant_id, nw_uname.strip(), nw_pw,
                        nw_rol, nw_fnaam.strip(), rechten,
                    )
                    if gelukt:
                        st.success(f"**{nw_uname.strip()}** aangemaakt.")
                        st.rerun()
                    else:
                        st.error("Aanmaken mislukt — gebruikersnaam bestaat mogelijk al.")
