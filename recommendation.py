"""Bestelengine — percentage buffer, pack-rounding, party platters, ratio multipliers.

V2 aanpassingen:
- bereken_dagen_tot_levering(): berekent dagen tot volgende leverdag per leverancier
- bereken_alle_adviezen(): verwachte_vraag schaalt nu met days_until_delivery
- Buffer: rechtstreeks uit buffer_pct per product (wizard bepaalt de waarde bij toevoegen)
"""
from __future__ import annotations
import math
from datetime import date, timedelta
import pandas as pd
from data_loader import FRIES_SKUS, DESSERT_SKUS, DRINKS_SKUS

# Weekdag-kolom volgorde (0=ma, 1=di, ..., 6=zo)
_LEVERDAGEN_KOLOMMEN = [
    "levert_ma", "levert_di", "levert_wo",
    "levert_do", "levert_vr", "levert_za", "levert_zo",
]

def bereken_dagen_tot_levering(
    leverancier_naam: str,
    vandaag: date,
    leveranciers: dict[str, dict],
) -> int:
    """
    Berekent het aantal dagen tot de eerstvolgende levering voor een leverancier.

    Regels:
    - Telling begint MORGEN (vandaag = leverdag telt niet mee)
    - Als geen leverancier gevonden of geen leverdagen ingesteld → fallback 1 dag
    - Zoekt maximaal 14 dagen vooruit

    Voorbeeld:
      Hanos levert di en do. Vandaag = ma → volgende levering = di = 1 dag.
      Hanos levert di en do. Vandaag = di → volgende levering = do = 2 dagen.
    """
    supplier = leveranciers.get(leverancier_naam)
    if not supplier:
        return 1

    leverdagen = [
        i for i, kolom in enumerate(_LEVERDAGEN_KOLOMMEN)
        if supplier.get(kolom, False)
    ]
    if not leverdagen:
        return 1

    for dag_offset in range(1, 15):
        kandidaat = vandaag + timedelta(days=dag_offset)
        if kandidaat.weekday() in leverdagen:
            return dag_offset

    return 1  # fallback als geen leverdag gevonden


def volgende_leverdag_info(
    leverancier_naam: str,
    vandaag: date,
    leveranciers: dict[str, dict],
) -> dict:
    """
    Geeft een dict terug met info over de volgende levering, voor weergave in de UI.
    Retourneert: {dagen: int, datum: date, weekdag_naam: str, te_laat_voor_bestel: bool}
    """
    WEEKDAGNAMEN_NL = ["maandag", "dinsdag", "woensdag", "donderdag",
                       "vrijdag", "zaterdag", "zondag"]
    supplier = leveranciers.get(leverancier_naam, {})
    lead_time = supplier.get("lead_time_days", 1) if supplier else 1
    dagen = bereken_dagen_tot_levering(leverancier_naam, vandaag, leveranciers)
    leverdatum = vandaag + timedelta(days=dagen)
    # Te laat voor bestellen als de levertijd groter of gelijk is aan de dagen tot levering
    te_laat = lead_time >= dagen
    return {
        "dagen":           dagen,
        "datum":           leverdatum,
        "weekdag_naam":    WEEKDAGNAMEN_NL[leverdatum.weekday()],
        "lead_time_days":  lead_time,
        "te_laat":         te_laat,
    }


# Extra minisnack-vraag per party platter (stuks)
PLATTER_25_EXTRA: dict[str, int] = {
    "SKU-023": 10,  # Frikandellen
    "SKU-025": 10,  # Kipnuggets
    "SKU-026": 5,   # Bitterballen
}
PLATTER_50_EXTRA: dict[str, int] = {
    "SKU-023": 20,
    "SKU-025": 20,
    "SKU-026": 10,
}


def _afronden_op_pack(hoeveelheid: float, pack_qty: float) -> float:
    if pack_qty <= 0:
        return float(math.ceil(hoeveelheid))
    return float(math.ceil(hoeveelheid / pack_qty) * pack_qty)


def genereer_reden(
    sku_id:             str,
    verwachte_vraag:    float,
    voorraad:           float,
    buffer_qty:         float,
    besteladvies:       float,
    event_naam:         str,
    fries_mult:         float,
    desserts_mult:      float,
    drinks_mult:        float,
    platter_extra:      float,
    dagen_tot_levering: int = 1,
) -> str:
    if besteladvies == 0:
        return (
            f"Voorraad {voorraad:.1f} volstaat "
            f"(vraag {verwachte_vraag:.1f} over {dagen_tot_levering}d + buffer {buffer_qty:.1f})"
        )

    tekort = verwachte_vraag + buffer_qty - voorraad
    reden  = (
        f"Vraag {dagen_tot_levering}d: {verwachte_vraag:.1f} "
        f"+ buffer {buffer_qty:.1f} − stock {voorraad:.1f} = {tekort:.1f} tekort"
    )

    toevoegingen = []
    if sku_id in FRIES_SKUS and fries_mult > 1.0:
        toevoegingen.append(f"friet-uplift ×{fries_mult:.2f}")
    if sku_id in DESSERT_SKUS and desserts_mult > 1.0:
        toevoegingen.append(f"dessert-uplift ×{desserts_mult:.2f}")
    if sku_id in DRINKS_SKUS and drinks_mult > 1.0:
        toevoegingen.append(f"terras-drankuplift ×{drinks_mult:.2f}")
    if platter_extra > 0:
        toevoegingen.append(f"+{platter_extra:.0f} partycatering")
    if event_naam != "geen event" and not toevoegingen:
        toevoegingen.append(event_naam)
    if toevoegingen:
        reden += " | " + ", ".join(toevoegingen)
    return reden


def bereken_alle_adviezen(
    df_producten:    pd.DataFrame,
    forecast_covers: int,
    df_stock:        pd.DataFrame,
    event_naam:      str   = "geen event",
    fries_mult:      float = 1.0,
    desserts_mult:   float = 1.0,
    drinks_mult:     float = 1.0,
    platters_25:     int   = 0,
    platters_50:     int   = 0,
    manager_overrides: dict[str, float] | None = None,
    leveranciers:    dict[str, dict] | None = None,
    vandaag:         date | None = None,
) -> pd.DataFrame:
    """
    Berekent besteladvies voor alle producten.

    V2 formule (met leveranciers/vandaag):
      verwachte_vraag = vraag_per_cover × forecast_covers × days_until_delivery
      buffer_qty      = verwachte_vraag × buffer_pct
      besteladvies    = max(0, verwachte_vraag + buffer_qty + platter_extra - voorraad)
                        → afgerond op verpakkingseenheid

    V1 formule (leveranciers=None of vandaag=None → fallback, days=1):
      Gedrag identiek aan vroeger — backward compatible.
    """
    if manager_overrides is None:
        manager_overrides = {}
    if leveranciers is None:
        leveranciers = {}
    if vandaag is None:
        vandaag = date.today()

    # Pre-bereken dagen per leverancier voor efficiency
    unieke_leveranciers = df_producten["leverancier"].unique()
    dagen_per_lev: dict[str, int] = {
        lev: bereken_dagen_tot_levering(lev, vandaag, leveranciers)
        for lev in unieke_leveranciers
    }

    df = df_producten.merge(
        df_stock[["product_id", "hoeveelheid"]].rename(columns={"hoeveelheid": "voorraad"}),
        left_on="id", right_on="product_id", how="left",
    ).copy()
    df["voorraad"] = df["voorraad"].fillna(0.0)

    # Voeg dagen_tot_levering toe als kolom voor gebruik in berekening en reden
    df["dagen_tot_levering"] = df["leverancier"].map(dagen_per_lev).fillna(1).astype(int)

    def vraag(row: pd.Series) -> float:
        sku   = row["id"]
        dagen = int(row["dagen_tot_levering"])
        base  = row["vraag_per_cover"] * forecast_covers * dagen
        if sku in FRIES_SKUS:
            base *= fries_mult
        if sku in DESSERT_SKUS:
            base *= desserts_mult
        if sku in DRINKS_SKUS:
            base *= drinks_mult
        return round(base, 3)

    def platter_extra(row: pd.Series) -> float:
        sku = row["id"]
        return (PLATTER_25_EXTRA.get(sku, 0) * platters_25 +
                PLATTER_50_EXTRA.get(sku, 0) * platters_50)

    df["verwachte_vraag"] = df.apply(vraag, axis=1)
    df["platter_extra"]   = df.apply(platter_extra, axis=1)

    # Buffer: rechtstreeks buffer_pct per product — wizard bepaalt dit bij toevoegen
    df["buffer_qty"] = df.apply(
        lambda r: round(r["verwachte_vraag"] * r["buffer_pct"], 3),
        axis=1,
    )
    df["bruto_behoefte"] = (
        df["verwachte_vraag"] + df["buffer_qty"] + df["platter_extra"] - df["voorraad"]
    )

    def advies(row: pd.Series) -> float:
        sku = row["id"]
        if sku in manager_overrides:
            return float(manager_overrides[sku])
        if row["bruto_behoefte"] <= 0:
            return 0.0
        return _afronden_op_pack(row["bruto_behoefte"], row["verpakkingseenheid"])

    df["besteladvies"] = df.apply(advies, axis=1)

    df["reden"] = df.apply(
        lambda r: genereer_reden(
            r["id"], r["verwachte_vraag"], r["voorraad"],
            r["buffer_qty"], r["besteladvies"],
            event_naam, fries_mult, desserts_mult, drinks_mult,
            r["platter_extra"], int(r["dagen_tot_levering"]),
        ),
        axis=1,
    )

    kolommen = ["id", "naam", "leverancier", "eenheid",
                "voorraad", "verwachte_vraag", "buffer_qty",
                "platter_extra", "dagen_tot_levering", "besteladvies", "reden"]
    return df[kolommen].reset_index(drop=True)


def groepeer_per_leverancier(df_advies: pd.DataFrame) -> dict[str, pd.DataFrame]:
    te_bestellen = df_advies[df_advies["besteladvies"] > 0]
    return {
        lev: groep[["id", "naam", "eenheid", "besteladvies"]].reset_index(drop=True)
        for lev, groep in te_bestellen.groupby("leverancier")
    }
