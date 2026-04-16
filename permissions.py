"""Rechten en rollen hiërarchie voor de besteltool."""
from __future__ import annotations

# Hiërarchie: hogere index = meer rechten
ROLLEN: list[str] = ["user", "manager", "admin", "super_admin"]

# Alle rechten gegroepeerd per categorie
RECHTEN_CATEGORIEËN: dict[str, dict[str, str]] = {
    "Uitvoerende taken": {
        "voorraad_tellen":       "Voorraad tellen / invoeren",
        "closing_invoeren":      "Dag afsluiten invoeren",
        "bestellingen_plaatsen": "Bestellingen versturen",
    },
    "Restaurant management": {
        "producten_beheren":    "Producten toevoegen / wijzigen",
        "leveranciers_beheren": "Leveranciers beheren",
        "forecast_aanpassen":   "Forecast handmatig bijsturen",
    },
    "App management": {
        "gebruikers_aanmaken": "Nieuwe gebruikers aanmaken",
        "gebruikers_beheren":  "Gebruikers bewerken / deactiveren",
        "rollen_toewijzen":    "Rollen toewijzen (→ manager)",
    },
}

# Rechten die een manager standaard heeft zonder extra toewijzing
MANAGER_STANDAARD = frozenset({
    "voorraad_tellen", "closing_invoeren", "bestellingen_plaatsen",
    "producten_beheren", "leveranciers_beheren", "forecast_aanpassen",
})

APP_MANAGEMENT_RECHTEN = frozenset({
    "gebruikers_aanmaken", "gebruikers_beheren", "rollen_toewijzen",
})

ROL_LABELS: dict[str, str] = {
    "user":        "Medewerker",
    "manager":     "Manager",
    "admin":       "Admin",
    "super_admin": "Super Admin",
}


def rol_label(rol: str) -> str:
    return ROL_LABELS.get(rol, rol)


def rol_index(rol: str) -> int:
    try:
        return ROLLEN.index(rol)
    except ValueError:
        return -1


def heeft_recht(recht: str, rol: str, permissions: dict) -> bool:
    """True als de gebruiker het opgegeven recht heeft."""
    if rol in ("admin", "super_admin"):
        return True
    if rol == "manager":
        return recht in MANAGER_STANDAARD or bool(permissions.get(recht, False))
    return bool(permissions.get(recht, False))


def kan_gebruiker_zien(actor_rol: str, target_rol: str) -> bool:
    """Actor mag target alleen zien als actor hoger in hiërarchie staat."""
    return rol_index(actor_rol) > rol_index(target_rol)


def kan_rol_wijzigen(actor_rol: str, target_rol: str, nieuwe_rol: str) -> bool:
    """
    True als actor de target van target_rol naar nieuwe_rol mag wijzigen.
    Regels: actor moet hoger staan dan zowel huidige als nieuwe rol.
    """
    actor_idx  = rol_index(actor_rol)
    target_idx = rol_index(target_rol)
    nieuwe_idx = rol_index(nieuwe_rol)
    return actor_idx > target_idx and actor_idx > nieuwe_idx


def beschikbare_rollen(actor_rol: str) -> list[str]:
    """Rollen die actor aan iemand anders mag toewijzen (lager dan zichzelf)."""
    actor_idx = rol_index(actor_rol)
    return [r for r in ROLLEN if rol_index(r) < actor_idx]


def kan_rechten_categorie_bewerken(actor_rol: str, categorie: str) -> bool:
    """True als actor de rechten in de opgegeven categorie mag wijzigen."""
    if actor_rol in ("admin", "super_admin"):
        return True
    if actor_rol == "manager":
        return categorie != "App management"
    return False
