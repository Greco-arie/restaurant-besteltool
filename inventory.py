"""
Inventarisbeheer — live voorraad, dagverbruik en handmatige correcties.

Architectuur:
- current_inventory  : live staat per (tenant_id, sku_id), altijd de meest recente waarde
- inventory_adjustments : onveranderlijk audit trail van elke wijziging
- daily_usage        : theoretisch verbruik per dag (op basis van bonnen × vraag_per_cover)

Sluitflow:
  1. Manager telt voorraad → sla_sluitstock_op() schrijft manager-telling naar current_inventory
  2. Systeem logt theoretisch verbruik in daily_usage (leermodel)
  3. Delta tussen theoretisch en werkelijk telt als leersignaal

Inventaris tab:
  Manager corrigeert live voorraad → sla_handmatige_correctie_op()
"""
from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
import db

# ── Signaalredenen ────────────────────────────────────────────────────────
# Redenen die wijzen op structurele verspilling (marge waarschijnlijk te hoog)
REDENEN_MARGE_TE_HOOG: frozenset[str] = frozenset({
    "Verspilling — verlopen / over datum",
    "Verspilling — beschadigd / gemorst",
})

# Redenen die wijzen op te krappe bestelling (marge of bestelfrequentie te laag)
REDENEN_MARGE_TE_LAAG: frozenset[str] = frozenset({
    "Sneller op dan verwacht",
})


# ── Live voorraad ─────────────────────────────────────────────────────────

def laad_huidige_voorraad(tenant_id: str) -> pd.DataFrame:
    """Laad live voorraad voor een tenant. Geeft lege DF terug bij geen data."""
    try:
        resp = (
            db.get_client()
            .table("current_inventory")
            .select("sku_id, current_stock, unit, last_updated_at, last_updated_by")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not resp.data:
            return pd.DataFrame(columns=["sku_id", "current_stock", "unit", "last_updated_at"])
        return pd.DataFrame(resp.data)
    except Exception:
        return pd.DataFrame(columns=["sku_id", "current_stock", "unit", "last_updated_at"])


def sla_sluitstock_op(
    tenant_id:   str,
    df_stock:    pd.DataFrame,
    datum:       date,
    created_by:  str = "manager",
) -> None:
    """
    Sla de door de manager getelde sluitstock op als live voorraad.
    df_stock verwacht kolommen: product_id, hoeveelheid.
    Dit is de gezaghebbende telling — overschrijft eerdere waarden.
    """
    sb = db.get_client()
    huidig_df = laad_huidige_voorraad(tenant_id)
    stock_map  = (
        dict(zip(huidig_df["sku_id"], huidig_df["current_stock"].astype(float)))
        if not huidig_df.empty else {}
    )

    upsert_rows    = []
    adjustment_rows = []

    for _, row in df_stock.iterrows():
        sku_id       = str(row["product_id"])
        nieuwe_stock = float(row["hoeveelheid"])
        oude_stock   = stock_map.get(sku_id, 0.0)
        delta        = round(nieuwe_stock - oude_stock, 3)

        upsert_rows.append({
            "tenant_id":       tenant_id,
            "sku_id":          sku_id,
            "current_stock":   nieuwe_stock,
            "last_updated_by": created_by,
        })
        adjustment_rows.append({
            "tenant_id":      tenant_id,
            "sku_id":         sku_id,
            "adjustment_type":"stock_count",
            "quantity_delta": delta,
            "previous_stock": oude_stock,
            "new_stock":      nieuwe_stock,
            "reason":         f"Sluittelling {datum.isoformat()}",
            "note":           "",
            "created_by":     created_by,
        })

    if upsert_rows:
        sb.table("current_inventory").upsert(
            upsert_rows, on_conflict="tenant_id,sku_id"
        ).execute()
    if adjustment_rows:
        sb.table("inventory_adjustments").insert(adjustment_rows).execute()


# ── Dagverbruik loggen (leermodel) ────────────────────────────────────────

def log_theoretisch_verbruik(
    tenant_id:     str,
    usage_date:    date,
    actual_covers: int,
    df_products:   pd.DataFrame,
) -> None:
    """
    Log theoretisch verbruik per SKU op basis van bonnen × vraag_per_cover.
    Slaat NIET current_inventory aan — de manager-telling is gezaghebbend.
    Wordt later gebruikt om forecast-aannames te ijken.
    """
    if actual_covers <= 0:
        return

    usage_datum_str = usage_date.isoformat()
    usage_rows = [
        {
            "tenant_id":         tenant_id,
            "usage_date":        usage_datum_str,
            "sku_id":            str(row["id"]),
            "theoretical_usage": round(float(row.get("vraag_per_cover", 0)) * actual_covers, 3),
            "actual_covers":     actual_covers,
        }
        for _, row in df_products.iterrows()
        if float(row.get("vraag_per_cover", 0)) > 0
    ]
    if usage_rows:
        db.get_client().table("daily_usage").upsert(
            usage_rows, on_conflict="tenant_id,usage_date,sku_id"
        ).execute()


# ── Handmatige correctie (inventaris tab) ────────────────────────────────

def sla_handmatige_correctie_op(
    tenant_id:    str,
    sku_id:       str,
    nieuwe_stock: float,
    reden:        str,
    notitie:      str,
    created_by:   str,
) -> None:
    """
    Sla een door de manager handmatig ingevoerde voorraadcorrectie op.
    Update current_inventory en schrijft een audit record.
    """
    sb = db.get_client()

    resp = (
        sb.table("current_inventory")
        .select("current_stock")
        .eq("tenant_id", tenant_id)
        .eq("sku_id", sku_id)
        .execute()
    )
    previous_stock = float(resp.data[0]["current_stock"]) if resp.data else 0.0
    delta          = round(nieuwe_stock - previous_stock, 3)

    sb.table("current_inventory").upsert({
        "tenant_id":       tenant_id,
        "sku_id":          sku_id,
        "current_stock":   nieuwe_stock,
        "last_updated_by": created_by,
    }, on_conflict="tenant_id,sku_id").execute()

    sb.table("inventory_adjustments").insert({
        "tenant_id":      tenant_id,
        "sku_id":         sku_id,
        "adjustment_type":"manual_correction",
        "quantity_delta": delta,
        "previous_stock": previous_stock,
        "new_stock":      nieuwe_stock,
        "reason":         reden,
        "note":           notitie,
        "created_by":     created_by,
    }).execute()


# ── Recente correcties ────────────────────────────────────────────────────

def laad_recente_correcties(tenant_id: str, limit: int = 15) -> pd.DataFrame:
    """Laad de meest recente inventarismutaties voor een tenant."""
    try:
        resp = (
            db.get_client()
            .table("inventory_adjustments")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ── Leersignalen ──────────────────────────────────────────────────────────

def laad_verbruik_analyse(tenant_id: str) -> pd.DataFrame:
    """
    Vergelijk theoretisch verbruik (daily_usage) met manager-correcties
    (inventory_adjustments type=stock_count) om afwijkingen per SKU te zien.
    """
    try:
        usage_resp = (
            db.get_client()
            .table("daily_usage")
            .select("sku_id, theoretical_usage, actual_covers, usage_date")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not usage_resp.data:
            return pd.DataFrame()

        df = pd.DataFrame(usage_resp.data)
        df["usage_per_cover"] = (
            df["theoretical_usage"].astype(float) / df["actual_covers"].astype(float)
        ).where(df["actual_covers"].astype(float) > 0)

        return (
            df.groupby("sku_id")
            .agg(
                datapunten    = ("usage_date",        "count"),
                gem_verbruik  = ("theoretical_usage", "mean"),
                gem_per_cover = ("usage_per_cover",   "mean"),
            )
            .reset_index()
            .sort_values("datapunten", ascending=False)
        )
    except Exception:
        return pd.DataFrame()


# ── Verspilling- en tekort-signalen ───────────────────────────────────────

def laad_verspilling_signalen(
    tenant_id: str,
    dagen:     int = 30,
    drempel:   int = 3,
) -> dict[str, dict]:
    """
    Analyseer handmatige correcties van de afgelopen `dagen` dagen.

    Geeft per SKU terug hoeveel keer een signaalreden voorkwam:
      {"marge_te_hoog": int, "marge_te_laag": int}

    Alleen SKUs met minstens één signaaltype >= drempel worden teruggegeven.

    marge_te_hoog  → product wordt structureel weggegooid (verlopen/beschadigd)
    marge_te_laag  → product raakt te snel op
    """
    cutoff = (date.today() - timedelta(days=dagen)).isoformat()
    try:
        resp = (
            db.get_client()
            .table("inventory_adjustments")
            .select("sku_id, reason")
            .eq("tenant_id", tenant_id)
            .eq("adjustment_type", "manual_correction")
            .gte("created_at", cutoff)
            .execute()
        )
        if not resp.data:
            return {}

        tellers: dict[str, dict] = {}
        for row in resp.data:
            sku   = row["sku_id"]
            reden = row.get("reason", "")
            if sku not in tellers:
                tellers[sku] = {"marge_te_hoog": 0, "marge_te_laag": 0}
            if reden in REDENEN_MARGE_TE_HOOG:
                tellers[sku]["marge_te_hoog"] += 1
            elif reden in REDENEN_MARGE_TE_LAAG:
                tellers[sku]["marge_te_laag"] += 1

        return {
            sku: counts
            for sku, counts in tellers.items()
            if counts["marge_te_hoog"] >= drempel or counts["marge_te_laag"] >= drempel
        }
    except Exception:
        return {}
