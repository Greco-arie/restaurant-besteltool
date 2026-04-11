"""
Leermodule — bijhoudt forecast vs. werkelijk resultaat per weekdag.

Werking:
- forecast_log.csv groeit elke dag met 1 rij
- bereken_correctiefactor() levert een factor per weekdag (bijv. 1.08 = systeem zat 8% te laag)
- forecast.py past de baseline aan met die factor
- Begrensd op 0.75–1.30 zodat het systeem niet doorslaat

Geen ML, geen black-box. Elke correctie is herleidbaar tot concrete dagdata.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from datetime import date

LOG_PATH = Path(__file__).parent / "data" / "forecast_log.csv"
LOG_COLS  = ["datum", "weekdag", "event_naam", "predicted_covers",
             "actual_covers", "omzet_werkelijk", "notitie"]

CORRECTIE_MIN  = 0.75
CORRECTIE_MAX  = 1.30
MIN_DATAPUNTEN = 3   # minimum rijen per weekdag voordat correctie actief is
N_RECENTE      = 8   # gebruik de laatste N vergelijkbare weekdagen


def _init_log() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        pd.DataFrame(columns=LOG_COLS).to_csv(LOG_PATH, index=False)


def log_forecast(
    datum_morgen:     date,
    predicted_covers: int,
    event_naam:       str,
    notitie:          str = "",
) -> None:
    """Sla de forecast op voor morgen. actual_covers en omzet_werkelijk zijn nog leeg."""
    _init_log()
    df = pd.read_csv(LOG_PATH)

    datum_str = datum_morgen.isoformat()
    weekdag   = datum_morgen.weekday()

    # Overschrijf als de datum al bestaat (bijv. bij herberekening)
    df = df[df["datum"] != datum_str]

    nieuwe_rij = pd.DataFrame([{
        "datum":            datum_str,
        "weekdag":          weekdag,
        "event_naam":       event_naam,
        "predicted_covers": predicted_covers,
        "actual_covers":    None,
        "omzet_werkelijk":  None,
        "notitie":          notitie.strip(),
    }])
    df = pd.concat([df, nieuwe_rij], ignore_index=True)
    df.to_csv(LOG_PATH, index=False)


def log_werkelijk(
    datum:           date,
    actual_covers:   int,
    omzet_werkelijk: float,
) -> bool:
    """Vul het werkelijke resultaat in voor een eerder gelogde dag. Geeft True als gevonden."""
    _init_log()
    df = pd.read_csv(LOG_PATH)
    datum_str = datum.isoformat()

    mask = df["datum"] == datum_str
    if not mask.any():
        return False

    df.loc[mask, "actual_covers"]   = actual_covers
    df.loc[mask, "omzet_werkelijk"] = omzet_werkelijk
    df.to_csv(LOG_PATH, index=False)
    return True


def bereken_correctiefactor(weekdag: int) -> tuple[float, str]:
    """
    Geeft (correctiefactor, uitleg) terug voor de gegeven weekdag.
    Factor = gemiddelde van (actual / predicted) over de laatste N_RECENTE voltooide rijen.
    Alleen actief als MIN_DATAPUNTEN of meer rijen beschikbaar zijn met werkelijke data.
    """
    _init_log()
    df = pd.read_csv(LOG_PATH)

    # Filter: zelfde weekdag, both values aanwezig
    df = df[
        (df["weekdag"] == weekdag) &
        (df["actual_covers"].notna()) &
        (df["predicted_covers"].notna()) &
        (df["predicted_covers"] > 0)
    ].copy()
    df = df.sort_values("datum", ascending=False).head(N_RECENTE)

    if len(df) < MIN_DATAPUNTEN:
        uitleg = (
            f"Nog geen correctiefactor actief ({len(df)}/{MIN_DATAPUNTEN} "
            f"datapunten voor deze weekdag)"
        )
        return 1.0, uitleg

    df["ratio"] = df["actual_covers"].astype(float) / df["predicted_covers"].astype(float)
    factor_raw  = float(df["ratio"].mean())
    factor      = round(max(CORRECTIE_MIN, min(CORRECTIE_MAX, factor_raw)), 4)

    richting = "te laag" if factor > 1.0 else "te hoog"
    uitleg   = (
        f"Correctiefactor op basis van {len(df)} datapunten: systeem voorspelde "
        f"gemiddeld {abs(factor_raw - 1) * 100:.1f}% {richting} → factor {factor:.3f}"
    )
    return factor, uitleg


def laad_accuracy_overzicht() -> pd.DataFrame | None:
    """Geeft een overzicht van forecast-accuraatheid per weekdag voor de UI."""
    _init_log()
    df = pd.read_csv(LOG_PATH)
    df = df[
        df["actual_covers"].notna() &
        df["predicted_covers"].notna() &
        (df["predicted_covers"] > 0)
    ].copy()

    if df.empty:
        return None

    df["predicted_covers"] = df["predicted_covers"].astype(float)
    df["actual_covers"]    = df["actual_covers"].astype(float)
    df["afwijking_pct"]    = ((df["actual_covers"] - df["predicted_covers"])
                              / df["predicted_covers"] * 100).round(1)
    df["abs_afwijking_pct"]= df["afwijking_pct"].abs()

    WEEKDAGNAMEN = ["Ma","Di","Wo","Do","Vr","Za","Zo"]
    overzicht = (
        df.groupby("weekdag")
        .agg(
            datapunten      = ("datum",           "count"),
            gemiddelde_fout = ("afwijking_pct",   "mean"),
            mae_pct         = ("abs_afwijking_pct","mean"),
            correctiefactor = ("actual_covers",
                               lambda x: round(max(CORRECTIE_MIN, min(CORRECTIE_MAX,
                                   (x.values / df.loc[x.index, "predicted_covers"].values).mean()
                               )), 3)),
        )
        .reset_index()
    )
    overzicht["weekdag_naam"]   = overzicht["weekdag"].map(lambda d: WEEKDAGNAMEN[d])
    overzicht["gemiddelde_fout"]= overzicht["gemiddelde_fout"].round(1)
    overzicht["mae_pct"]        = overzicht["mae_pct"].round(1)
    return overzicht[[
        "weekdag_naam","datapunten","gemiddelde_fout","mae_pct","correctiefactor"
    ]].rename(columns={
        "weekdag_naam":   "Weekdag",
        "datapunten":     "Datapunten",
        "gemiddelde_fout":"Gem. afwijking %",
        "mae_pct":        "Gem. abs. fout %",
        "correctiefactor":"Correctiefactor",
    })


def laad_notitie_analyse() -> pd.DataFrame | None:
    """
    Geeft een tabel terug van unieke notities met hun gemiddelde afwijking.
    Alleen rijen met ingevuld werkelijk resultaat én een notitie.
    Minimum 2 datapunten per notitie om ruis te vermijden.
    """
    _init_log()
    df = pd.read_csv(LOG_PATH)
    df = df[
        df["actual_covers"].notna() &
        df["predicted_covers"].notna() &
        (df["predicted_covers"] > 0) &
        df["notitie"].notna() &
        (df["notitie"].str.strip() != "")
    ].copy()

    if df.empty:
        return None

    df["predicted_covers"] = df["predicted_covers"].astype(float)
    df["actual_covers"]    = df["actual_covers"].astype(float)
    df["afwijking_pct"]    = ((df["actual_covers"] - df["predicted_covers"])
                              / df["predicted_covers"] * 100).round(1)

    analyse = (
        df.groupby("notitie")
        .agg(
            keren          = ("datum",        "count"),
            gem_afwijking  = ("afwijking_pct","mean"),
            gem_werkelijk  = ("actual_covers","mean"),
        )
        .reset_index()
        .sort_values("keren", ascending=False)
    )
    # Alleen notities met 2+ datapunten tonen
    analyse = analyse[analyse["keren"] >= 2].copy()
    if analyse.empty:
        return None

    analyse["gem_afwijking"] = analyse["gem_afwijking"].round(1)
    analyse["gem_werkelijk"] = analyse["gem_werkelijk"].round(0).astype(int)
    return analyse.rename(columns={
        "notitie":       "Notitie",
        "keren":         "Keren genoteerd",
        "gem_afwijking": "Gem. afwijking %",
        "gem_werkelijk": "Gem. werkelijk (bonnen)",
    })


def heeft_open_werkelijk(datum: date) -> bool:
    """True als er een forecast-rij is voor deze datum zonder werkelijk resultaat."""
    _init_log()
    df = pd.read_csv(LOG_PATH)
    datum_str = datum.isoformat()
    rij = df[df["datum"] == datum_str]
    if rij.empty:
        return False
    return bool(rij["actual_covers"].isna().any())
