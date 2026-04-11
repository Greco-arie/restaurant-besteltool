"""
Leermodule — bijhoudt forecast vs. werkelijk resultaat per weekdag, tenant-aware.

Werking:
- Elke dag groeit forecast_log met 1 rij (predicted_covers)
- Manager vult werkelijke bonnen in → actual_covers
- bereken_correctiefactor() levert factor per weekdag per tenant
- Begrensd op 0.75–1.30 zodat het systeem niet doorslaat
"""
from __future__ import annotations
from datetime import date
import pandas as pd
import db

CORRECTIE_MIN  = 0.75
CORRECTIE_MAX  = 1.30
MIN_DATAPUNTEN = 3
N_RECENTE      = 8


def _alle_logs(tenant_id: str) -> pd.DataFrame:
    """Laad alle forecast_log rijen voor een tenant."""
    try:
        resp = (
            db.get_client()
            .table("forecast_log")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("datum")
            .execute()
        )
        if not resp.data:
            return pd.DataFrame(columns=[
                "datum", "weekdag", "event_naam", "predicted_covers",
                "actual_covers", "omzet_werkelijk", "notitie",
            ])
        return pd.DataFrame(resp.data)
    except Exception:
        return pd.DataFrame(columns=[
            "datum", "weekdag", "event_naam", "predicted_covers",
            "actual_covers", "omzet_werkelijk", "notitie",
        ])


def log_forecast(
    tenant_id:        str,
    datum_morgen:     date,
    predicted_covers: int,
    event_naam:       str,
    notitie:          str = "",
) -> None:
    """Sla de forecast op. actual_covers en omzet_werkelijk zijn nog leeg."""
    db.get_client().table("forecast_log").upsert({
        "tenant_id":        tenant_id,
        "datum":            datum_morgen.isoformat(),
        "weekdag":          datum_morgen.weekday(),
        "event_naam":       event_naam,
        "predicted_covers": predicted_covers,
        "actual_covers":    None,
        "omzet_werkelijk":  None,
        "notitie":          notitie.strip(),
    }, on_conflict="datum,tenant_id").execute()


def log_werkelijk(
    tenant_id:       str,
    datum:           date,
    actual_covers:   int,
    omzet_werkelijk: float,
) -> bool:
    """Vul het werkelijke resultaat in voor een eerder gelogde dag. True als gevonden."""
    datum_str = datum.isoformat()
    sb = db.get_client()
    resp = (
        sb.table("forecast_log")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("datum", datum_str)
        .execute()
    )
    if not resp.data:
        return False
    sb.table("forecast_log").update({
        "actual_covers":   actual_covers,
        "omzet_werkelijk": omzet_werkelijk,
    }).eq("tenant_id", tenant_id).eq("datum", datum_str).execute()
    return True


def bereken_correctiefactor(tenant_id: str, weekdag: int) -> tuple[float, str]:
    """
    Geeft (correctiefactor, uitleg) terug voor de gegeven weekdag en tenant.
    Factor = gemiddelde van actual/predicted over de laatste N_RECENTE voltooide rijen.
    """
    df = _alle_logs(tenant_id)
    df = df[
        (df["weekdag"] == weekdag) &
        df["actual_covers"].notna() &
        df["predicted_covers"].notna()
    ].copy()
    df = df[df["predicted_covers"].astype(float) > 0]
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


def laad_accuracy_overzicht(tenant_id: str) -> pd.DataFrame | None:
    """Overzicht van forecast-accuraatheid per weekdag voor de UI."""
    df = _alle_logs(tenant_id)
    df = df[df["actual_covers"].notna() & df["predicted_covers"].notna()].copy()
    df = df[df["predicted_covers"].astype(float) > 0]

    if df.empty:
        return None

    df["predicted_covers"]  = df["predicted_covers"].astype(float)
    df["actual_covers"]     = df["actual_covers"].astype(float)
    df["weekdag"]           = df["weekdag"].astype(int)
    df["afwijking_pct"]     = ((df["actual_covers"] - df["predicted_covers"])
                               / df["predicted_covers"] * 100).round(1)
    df["abs_afwijking_pct"] = df["afwijking_pct"].abs()

    WEEKDAGNAMEN = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
    overzicht = (
        df.groupby("weekdag")
        .agg(
            datapunten      = ("datum",            "count"),
            gemiddelde_fout = ("afwijking_pct",    "mean"),
            mae_pct         = ("abs_afwijking_pct","mean"),
            correctiefactor = ("actual_covers",
                               lambda x: round(max(CORRECTIE_MIN, min(CORRECTIE_MAX,
                                   (x.values / df.loc[x.index, "predicted_covers"].values).mean()
                               )), 3)),
        )
        .reset_index()
    )
    overzicht["weekdag_naam"]    = overzicht["weekdag"].map(lambda d: WEEKDAGNAMEN[d])
    overzicht["gemiddelde_fout"] = overzicht["gemiddelde_fout"].round(1)
    overzicht["mae_pct"]         = overzicht["mae_pct"].round(1)
    return overzicht[[
        "weekdag_naam", "datapunten", "gemiddelde_fout", "mae_pct", "correctiefactor"
    ]].rename(columns={
        "weekdag_naam":   "Weekdag",
        "datapunten":     "Datapunten",
        "gemiddelde_fout":"Gem. afwijking %",
        "mae_pct":        "Gem. abs. fout %",
        "correctiefactor":"Correctiefactor",
    })


def laad_notitie_analyse(tenant_id: str) -> pd.DataFrame | None:
    """Unieke notities met gemiddelde afwijking. Minimum 2 datapunten."""
    df = _alle_logs(tenant_id)
    df = df[
        df["actual_covers"].notna() &
        df["predicted_covers"].notna() &
        df["notitie"].notna() &
        (df["notitie"].astype(str).str.strip() != "")
    ].copy()
    df = df[df["predicted_covers"].astype(float) > 0]

    if df.empty:
        return None

    df["predicted_covers"] = df["predicted_covers"].astype(float)
    df["actual_covers"]    = df["actual_covers"].astype(float)
    df["afwijking_pct"]    = ((df["actual_covers"] - df["predicted_covers"])
                              / df["predicted_covers"] * 100).round(1)

    analyse = (
        df.groupby("notitie")
        .agg(
            keren         = ("datum",        "count"),
            gem_afwijking = ("afwijking_pct","mean"),
            gem_werkelijk = ("actual_covers","mean"),
        )
        .reset_index()
        .sort_values("keren", ascending=False)
    )
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


def heeft_open_werkelijk(tenant_id: str, datum: date) -> bool:
    """True als er een forecast-rij bestaat voor deze datum zonder werkelijk resultaat."""
    try:
        datum_str = datum.isoformat()
        resp = (
            db.get_client()
            .table("forecast_log")
            .select("actual_covers")
            .eq("tenant_id", tenant_id)
            .eq("datum", datum_str)
            .execute()
        )
        if not resp.data:
            return False
        return resp.data[0]["actual_covers"] is None
    except Exception:
        return False
