"""Forecastengine — baseline + event multipliers + reserveringen + lerende correctie + weer."""
from __future__ import annotations
from datetime import date
import pandas as pd
import learning
import weather

WEEKDAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def bereken_baseline(
    df_history: pd.DataFrame, weekdag: int, n: int = 4, fallback: float = 200.0
) -> float:
    """Gemiddelde covers van de laatste n vergelijkbare weekdagen."""
    vergelijkbaar = (
        df_history[df_history["weekdag"] == weekdag]
        .sort_values("datum", ascending=False)
        .head(n)
    )
    if vergelijkbaar.empty:
        overall = df_history["covers"].mean()
        return float(overall) if not pd.isna(overall) else fallback
    return float(vergelijkbaar["covers"].mean())


def bereken_trend(df_history: pd.DataFrame, n_dagen: int = 14) -> float:
    """Trend als factor t.o.v. vorige periode (begrensd op 0.7–1.4)."""
    vandaag = pd.Timestamp(date.today())
    grens1  = vandaag - pd.Timedelta(days=n_dagen)
    grens2  = vandaag - pd.Timedelta(days=n_dagen * 2)

    recent = df_history[df_history["datum"] >= grens1]["covers"].mean()
    eerder = df_history[
        (df_history["datum"] >= grens2) & (df_history["datum"] < grens1)
    ]["covers"].mean()

    if pd.isna(eerder) or eerder == 0 or pd.isna(recent):
        return 1.0
    return float(max(0.7, min(1.4, recent / eerder)))


def bereken_reserveringscorrectie(
    reserved_covers: int, df_history: pd.DataFrame, weekdag_morgen: int
) -> float:
    """Factor op basis van geplande covers t.o.v. normaal voor die weekdag."""
    if reserved_covers == 0:
        return 1.0
    normaal = df_history[df_history["weekdag"] == weekdag_morgen]["covers"].mean()
    if pd.isna(normaal) or normaal == 0:
        return 1.0
    # Reserveringen zijn additioneel op de verwachte baseline
    factor = (normaal + reserved_covers) / normaal
    return float(max(0.8, min(2.0, factor)))


def bereken_event_factors(
    df_events: pd.DataFrame, datum_morgen: date
) -> tuple[float, float, float, str, str]:
    """Geeft (covers_mult, fries_mult, desserts_mult, event_naam, event_type) terug."""
    ts = pd.Timestamp(datum_morgen)
    match = df_events[df_events["datum"] == ts]
    if match.empty:
        return 1.0, 1.0, 1.0, "geen event", ""
    row = match.iloc[0]
    return (
        float(row["covers_multiplier"]),
        float(row["fries_ratio_multiplier"]),
        float(row["desserts_ratio_multiplier"]),
        str(row["event_name"]),
        str(row["event_type"]),
    )


def bereken_party_platter_extra(
    df_reservations: pd.DataFrame, datum_morgen: date
) -> tuple[int, int, int]:
    """Geeft (totaal_extra_covers, platters_25, platters_50) terug."""
    ts = pd.Timestamp(datum_morgen)
    rows = df_reservations[df_reservations["datum"] == ts]
    if rows.empty:
        return 0, 0, 0
    p25 = int(rows["party_platters_25"].sum())
    p50 = int(rows["party_platters_50"].sum())
    rc  = int(rows["reserved_covers"].sum())
    return rc, p25, p50


def bereken_confidence(df_history: pd.DataFrame, weekdag: int) -> str:
    n = len(df_history[df_history["weekdag"] == weekdag])
    if n >= 6:
        return "hoog"
    elif n >= 3:
        return "gemiddeld"
    return "laag"


def bereken_forecast(
    covers_vandaag:   int,
    omzet_vandaag:    float,
    reserved_covers:  int,
    bijzonderheden:   str,
    df_history:       pd.DataFrame,
    df_events:        pd.DataFrame,
    df_reservations:  pd.DataFrame,
    datum_morgen:     date,
    manager_override: int | None = None,
) -> dict:
    weekdag_morgen = datum_morgen.weekday()

    baseline     = bereken_baseline(df_history, weekdag_morgen,
                                    fallback=float(covers_vandaag) if covers_vandaag > 0 else 200.0)
    trend_factor = bereken_trend(df_history)
    res_factor   = bereken_reserveringscorrectie(reserved_covers, df_history, weekdag_morgen)
    covers_mult, fries_mult, desserts_mult, event_naam, event_type = \
        bereken_event_factors(df_events, datum_morgen)
    extra_rc, platters_25, platters_50 = \
        bereken_party_platter_extra(df_reservations, datum_morgen)
    confidence   = bereken_confidence(df_history, weekdag_morgen)

    correctie_factor, correctie_uitleg = learning.bereken_correctiefactor(weekdag_morgen)
    weer = weather.get_weer_morgen(datum_morgen)
    terras_factor = weer["terras_factor"]
    drinks_factor = weer["drinks_factor"]

    if manager_override and manager_override > 0:
        forecast_covers = manager_override
        override_actief = True
    else:
        forecast_covers = round(
            baseline * trend_factor * res_factor * covers_mult
            * correctie_factor * terras_factor
        )
        override_actief = False

    omzet_per_cover = omzet_vandaag / covers_vandaag if covers_vandaag > 0 else 15.0
    forecast_omzet  = round(forecast_covers * omzet_per_cover, 2)

    n_comp = len(df_history[df_history["weekdag"] == weekdag_morgen])
    drivers = [
        f"Baseline ({min(n_comp,4)} {WEEKDAGEN[weekdag_morgen]}en): "
        f"{baseline:.0f} bonnen gemiddeld",
        f"Trend (recente 2 weken): {(trend_factor - 1) * 100:+.1f}%",
        correctie_uitleg,
    ]
    if terras_factor != 1.0:
        drivers.append(
            f"Weer morgen: {weer['icon']} {weer['omschrijving']} "
            f"{weer['temp_max']:.0f}°C — terras ×{terras_factor:.2f}"
        )
    if reserved_covers > 0:
        drivers.append(f"Reserveringen morgen: +{reserved_covers} (factor {res_factor:.2f})")
    if event_naam != "geen event":
        drivers.append(
            f"Event: {event_naam} (covers ×{covers_mult:.2f}, "
            f"friet ×{fries_mult:.2f}, desserts ×{desserts_mult:.2f})"
        )
    if platters_25 or platters_50:
        drivers.append(
            f"Partycatering: {platters_25}× platter 25st + {platters_50}× platter 50st "
            f"— extra minisnack-vraag"
        )
    if override_actief:
        drivers.append(f"Manager override: {manager_override} bonnen (vervangt berekening)")
    if bijzonderheden.strip():
        drivers.append(f"Notitie manager: {bijzonderheden.strip()}")

    return {
        "datum_morgen":      datum_morgen,
        "weekdag_morgen":    weekdag_morgen,
        "forecast_covers":   forecast_covers,
        "forecast_omzet":    forecast_omzet,
        "confidence":        confidence,
        "drivers":           drivers,
        "baseline":          baseline,
        "trend_factor":      trend_factor,
        "res_factor":        res_factor,
        "covers_mult":       covers_mult,
        "fries_mult":        fries_mult,
        "desserts_mult":     desserts_mult,
        "event_naam":        event_naam,
        "event_type":        event_type,
        "platters_25":       platters_25,
        "platters_50":       platters_50,
        "override_actief":   override_actief,
        "correctie_factor":  correctie_factor,
        "correctie_uitleg":  correctie_uitleg,
        "terras_factor":     terras_factor,
        "drinks_factor":     drinks_factor,
        "weer":              weer,
    }
