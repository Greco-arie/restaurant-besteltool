"""Data loading + persistentie — tenant-aware, normaliseert en slaat dagdata op via Supabase."""
from pathlib import Path
from datetime import date
import pandas as pd
import db

DEMO_DIR = Path(__file__).parent / "demo_data"

FRIES_SKUS   = {"SKU-001", "SKU-002"}
DESSERT_SKUS = {"SKU-027", "SKU-028"}
DRINKS_SKUS  = {"SKU-029", "SKU-030"}


# ── Statische CSV data (niet tenant-specifiek) ────────────────────────────

def load_events() -> pd.DataFrame:
    df = pd.read_csv(DEMO_DIR / "events.csv", parse_dates=["date"])
    df = df.rename(columns={"date": "datum"})
    return df


def load_reservations(datum_str: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(DEMO_DIR / "reservations.csv", parse_dates=["date"])
    df = df.rename(columns={"date": "datum"})
    if datum_str:
        return df[df["datum"] == datum_str].reset_index(drop=True)
    return df


# ── Supabase: verkoophistorie (tenant-aware) ──────────────────────────────

def load_sales_history(tenant_id: str) -> pd.DataFrame:
    """Laad alle verkoopdagen voor de opgegeven tenant."""
    try:
        resp = (
            db.get_client()
            .table("sales_history")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("date")
            .execute()
        )
        if not resp.data:
            return pd.DataFrame(columns=["datum", "weekdag", "covers", "omzet"])
        df = pd.DataFrame(resp.data)
        df = df.rename(columns={"date": "datum", "revenue_eur": "omzet"})
        df["datum"]   = pd.to_datetime(df["datum"])
        df["weekdag"] = df["datum"].dt.day_of_week
        return df.sort_values("datum").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["datum", "weekdag", "covers", "omzet"])


def sla_dag_op(
    tenant_id:     str,
    datum:         date,
    covers:        int,
    omzet:         float,
    reserveringen: int = 0,
    notitie:       str = "",
) -> None:
    """Sla de closing-data op voor de gegeven tenant. Overschrijft als datum al bestaat."""
    WEEKDAGEN_ENG = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    db.get_client().table("sales_history").upsert({
        "tenant_id":   tenant_id,
        "date":        datum.isoformat(),
        "weekday":     WEEKDAGEN_ENG[datum.weekday()],
        "covers":      covers,
        "revenue_eur": omzet,
        "note":        notitie,
    }, on_conflict="date,tenant_id").execute()


# ── Supabase: voorraad (tenant-aware) ────────────────────────────────────

def load_stock_count(tenant_id: str) -> pd.DataFrame:
    """Laad meest recente voorraadtelling voor de opgegeven tenant."""
    try:
        sb = db.get_client()
        latest = (
            sb.table("stock_count")
            .select("date")
            .eq("tenant_id", tenant_id)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if not latest.data:
            return pd.DataFrame(columns=["product_id", "hoeveelheid"])

        resp = (
            sb.table("stock_count")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("date", latest.data[0]["date"])
            .execute()
        )
        if not resp.data:
            return pd.DataFrame(columns=["product_id", "hoeveelheid"])

        df = pd.DataFrame(resp.data)
        df = df.rename(columns={"sku_id": "product_id", "on_hand_qty": "hoeveelheid"})
        return df[["product_id", "hoeveelheid"]].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["product_id", "hoeveelheid"])


def sla_stock_op(tenant_id: str, datum: date, df_stock: pd.DataFrame) -> None:
    """
    Sla historische voorraadtelling op in stock_count.
    df_stock verwacht kolommen: product_id, hoeveelheid.
    """
    rows = [
        {
            "tenant_id":   tenant_id,
            "date":        datum.isoformat(),
            "sku_id":      row["product_id"],
            "on_hand_qty": float(row["hoeveelheid"]),
            "unit":        "",
            "note":        "manager closing",
        }
        for _, row in df_stock.iterrows()
    ]
    db.get_client().table("stock_count").upsert(
        rows, on_conflict="date,sku_id,tenant_id"
    ).execute()


