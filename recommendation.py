"""Bestelengine — percentage buffer, pack-rounding, party platters, ratio multipliers."""
from __future__ import annotations
import math
import pandas as pd
from data_loader import FRIES_SKUS, DESSERT_SKUS, DRINKS_SKUS

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
    sku_id:          str,
    verwachte_vraag: float,
    voorraad:        float,
    buffer_qty:      float,
    besteladvies:    float,
    event_naam:      str,
    fries_mult:      float,
    desserts_mult:   float,
    drinks_mult:     float,
    platter_extra:   float,
) -> str:
    if besteladvies == 0:
        return f"Voorraad {voorraad:.1f} volstaat (vraag {verwachte_vraag:.1f} + buffer {buffer_qty:.1f})"

    tekort = verwachte_vraag + buffer_qty - voorraad
    reden  = f"Vraag {verwachte_vraag:.1f} + buffer {buffer_qty:.1f} − stock {voorraad:.1f} = {tekort:.1f} tekort"

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
) -> pd.DataFrame:
    if manager_overrides is None:
        manager_overrides = {}

    df = df_producten.merge(
        df_stock[["product_id", "hoeveelheid"]].rename(columns={"hoeveelheid": "voorraad"}),
        left_on="id", right_on="product_id", how="left",
    ).copy()
    df["voorraad"] = df["voorraad"].fillna(0.0)

    def vraag(row: pd.Series) -> float:
        sku = row["id"]
        base = row["vraag_per_cover"] * forecast_covers
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
    df["buffer_qty"]      = (df["verwachte_vraag"] * df["buffer_pct"]).round(3)
    df["bruto_behoefte"]  = df["verwachte_vraag"] + df["buffer_qty"] + df["platter_extra"] - df["voorraad"]

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
            event_naam, fries_mult, desserts_mult, drinks_mult, r["platter_extra"],
        ),
        axis=1,
    )

    kolommen = ["id", "naam", "leverancier", "eenheid",
                "voorraad", "verwachte_vraag", "buffer_qty",
                "platter_extra", "besteladvies", "reden"]
    return df[kolommen].reset_index(drop=True)


def groepeer_per_leverancier(df_advies: pd.DataFrame) -> dict[str, pd.DataFrame]:
    te_bestellen = df_advies[df_advies["besteladvies"] > 0]
    return {
        lev: groep[["id", "naam", "eenheid", "besteladvies"]].reset_index(drop=True)
        for lev, groep in te_bestellen.groupby("leverancier")
    }
