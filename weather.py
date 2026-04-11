"""
Weermodule — haalt morgen's weersvoorspelling op voor Maarssen via Open-Meteo.

Geen API-key nodig. Geeft terras_factor (invloed op covers) en
drinks_factor (invloed op dranken) terug op basis van temperatuur en neerslag.

Terraslogica Family Maarssen — groot terras, bij goed weer ×1.4 capaciteit:
  ≥20°C + ≤30% regenrisico  → terras vol      → covers ×1.40, dranken ×1.60
  ≥15°C + ≤59% regenrisico  → terras gedeeltelijk → covers ×1.18, dranken ×1.30
  koud (<15°C) of regen      → terras dicht    → covers ×1.00, dranken ×1.00
"""
from __future__ import annotations
import urllib.request
import json
from datetime import date, timedelta
from functools import lru_cache

# Maarssen, Bisonspoor (Utrecht-omgeving)
LAT = 52.1367
LON = 5.0378

# WMO weather code → is het regen/slecht weer?
_SLECHT_WEER_CODES = frozenset([
    45, 48,                          # mist
    51, 53, 55, 56, 57,              # motregen
    61, 63, 65, 66, 67,              # regen
    71, 73, 75, 77,                  # sneeuw
    80, 81, 82,                      # buien
    85, 86,                          # sneeuwbuien
    95, 96, 99,                      # onweer
])

_WMO_OMSCHRIJVING = {
    0:  "Helder",
    1:  "Overwegend helder",
    2:  "Gedeeltelijk bewolkt",
    3:  "Bewolkt",
    45: "Mist",
    48: "IJsmist",
    51: "Lichte motregen",
    53: "Matige motregen",
    55: "Zware motregen",
    61: "Lichte regen",
    63: "Matige regen",
    65: "Zware regen",
    80: "Regenbuien",
    81: "Zware regenbuien",
    82: "Hevige buien",
    95: "Onweer",
    99: "Onweer met hagel",
}


@lru_cache(maxsize=1)
def _fetch_raw(morgen_str: str) -> dict | None:
    """Eenmalig ophalen per sessie (lru_cache op datum-string)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=temperature_2m_max,precipitation_probability_max,weathercode"
        "&timezone=Europe%2FAmsterdam"
        "&forecast_days=3"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _terras_scenario(
    temp_max: float, precip_prob: int, wmo_code: int
) -> tuple[float, float, str, str]:
    """Geeft (terras_factor, drinks_factor, label, icon) terug."""
    regen = wmo_code in _SLECHT_WEER_CODES or precip_prob >= 60
    warm  = temp_max >= 20
    mild  = temp_max >= 15

    if regen:
        return (
            1.0, 1.0,
            f"Regen/slecht weer ({precip_prob}% kans) — terras dicht",
            "🌧️",
        )
    if warm:
        return (
            1.40, 1.60,
            f"Warm & droog ({temp_max:.0f}°C, {precip_prob}% regenrisico) "
            f"— terras vol verwacht (+40% bonnen, +60% dranken)",
            "☀️",
        )
    if mild:
        return (
            1.18, 1.30,
            f"Aangenaam ({temp_max:.0f}°C, {precip_prob}% regenrisico) "
            f"— terras gedeeltelijk open (+18% bonnen, +30% dranken)",
            "⛅",
        )
    return (
        1.0, 1.0,
        f"Koud ({temp_max:.0f}°C) — terras dicht",
        "🌥️",
    )


def get_weer_morgen(datum_morgen: date | None = None) -> dict:
    """
    Geeft een dict terug met weerinformatie voor morgen:
        temp_max        float   max temperatuur °C
        precip_prob     int     regenrisico %
        wmo_code        int     WMO-weercode
        omschrijving    str     leesbare weerbeschrijving
        terras_factor   float   multiplier op forecast_covers
        drinks_factor   float   multiplier op dranken-SKUs
        label           str     uitleg voor de UI
        icon            str     emoji
        beschikbaar     bool    False als API niet bereikbaar was
    """
    morgen = datum_morgen or (date.today() + __import__("datetime").timedelta(days=1))
    morgen_str = morgen.isoformat()

    data = _fetch_raw(morgen_str)

    if data is None:
        return {
            "temp_max":      None,
            "precip_prob":   None,
            "wmo_code":      None,
            "omschrijving":  "Weerdata niet beschikbaar",
            "terras_factor": 1.0,
            "drinks_factor": 1.0,
            "label":         "Weer niet beschikbaar — geen terras-correctie toegepast",
            "icon":          "❓",
            "beschikbaar":   False,
        }

    try:
        dates = data["daily"]["time"]
        idx   = dates.index(morgen_str)
    except (KeyError, ValueError):
        idx = 1  # fallback: tweede dag (morgen)

    try:
        temp_max    = float(data["daily"]["temperature_2m_max"][idx])
        precip_prob = int(data["daily"]["precipitation_probability_max"][idx])
        wmo_code    = int(data["daily"]["weathercode"][idx])
    except (KeyError, IndexError, TypeError):
        return {
            "temp_max":      None,
            "precip_prob":   None,
            "wmo_code":      None,
            "omschrijving":  "Weerdata niet parseerbaar",
            "terras_factor": 1.0,
            "drinks_factor": 1.0,
            "label":         "Weerdata niet parseerbaar — geen terras-correctie",
            "icon":          "❓",
            "beschikbaar":   False,
        }

    terras_factor, drinks_factor, label, icon = _terras_scenario(
        temp_max, precip_prob, wmo_code
    )
    omschrijving = _WMO_OMSCHRIJVING.get(wmo_code, f"Code {wmo_code}")

    return {
        "temp_max":      temp_max,
        "precip_prob":   precip_prob,
        "wmo_code":      wmo_code,
        "omschrijving":  omschrijving,
        "terras_factor": terras_factor,
        "drinks_factor": drinks_factor,
        "label":         label,
        "icon":          icon,
        "beschikbaar":   True,
    }
