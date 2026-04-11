"""Data loading + persistentie — normaliseert en slaat dagdata op via Supabase."""
from pathlib import Path
from datetime import date
import pandas as pd

import db

DEMO_DIR = Path(__file__).parent / "demo_data"

SUPPLIER_NAMEN = {
    "wholesale": "Hanos",
    "fresh":     "Vers Leverancier",
    "bakery":    "Bakkersland",
    "beer":      "Heineken Distrib.",
}

# E-mailadres + aanhef per leverancier — pas aan naar werkelijke contactpersonen
SUPPLIER_CONFIG: dict[str, dict] = {
    "Hanos": {
        "email":    "inkoop@hanos.nl",
        "aanhef":   "Beste Hanos,",
    },
    "Vers Leverancier": {
        "email":    "orders@versleverancier.nl",
        "aanhef":   "Beste leverancier,",
    },
    "Bakkersland": {
        "email":    "orders@bakkersland.nl",
        "aanhef":   "Beste Bakkersland,",
    },
    "Heineken Distrib.": {
        "email":    "orders@heineken.nl",
        "aanhef":   "Beste Heineken,",
    },
}

# SKU-groepen voor ratio-multipliers
FRIES_SKUS   = {"SKU-001", "SKU-002"}
DESSERT_SKUS = {"SKU-027", "SKU-028"}
DRINKS_SKUS  = {"SKU-029", "SKU-030"}  # Cola + Heineken — terras-gevoelig


# ── Statische CSV data (producten, events, reserveringen) ─────────────────

def load_products() -> pd.DataFrame:
    df = pd.read_csv(DEMO_DIR / "products.csv")
    df = df.rename(columns={
        "sku_id":           "id",
        "sku_name":         "naam",
        "base_unit":        "eenheid",
        "pack_qty":         "verpakkingseenheid",
        "demand_per_cover": "vraag_per_cover",
        "min_stock":        "minimumvoorraad",
    })
    df["leverancier"] = df["supplier_type"].map(SUPPLIER_NAMEN).fillna("Overig")
    df["actief"] = 1
    return df.reset_index(drop=True)


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


# ── Supabase: verkoophistorie ─────────────────────────────────────────────

def load_sales_history() -> pd.DataFrame:
    """Laad alle verkoopdagen uit Supabase."""
    try:
        resp = db.get_client().table("sales_history").select("*").order("date").execute()
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
    datum:         date,
    covers:        int,
    omzet:         float,
    reserveringen: int = 0,
    notitie:       str = "",
) -> None:
    """Sla de closing-data op in Supabase. Overschrijft als de datum al bestaat."""
    WEEKDAGEN_ENG = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    db.get_client().table("sales_history").upsert({
        "date":        datum.isoformat(),
        "weekday":     WEEKDAGEN_ENG[datum.weekday()],
        "covers":      covers,
        "revenue_eur": omzet,
        "note":        notitie,
    }, on_conflict="date").execute()


# ── Supabase: voorraad ────────────────────────────────────────────────────

def load_stock_count(datum_str: str | None = None) -> pd.DataFrame:
    """
    Laad voorraadtelling uit Supabase.
    Zonder datum_str: meest recente dag. Fallback naar demo_data CSV als DB leeg is.
    """
    try:
        sb = db.get_client()
        if datum_str:
            resp = sb.table("stock_count").select("*").eq("date", datum_str).execute()
        else:
            # Meest recente datum ophalen
            latest = sb.table("stock_count").select("date").order("date", desc=True).limit(1).execute()
            if not latest.data:
                return _load_stock_count_csv()
            resp = sb.table("stock_count").select("*").eq("date", latest.data[0]["date"]).execute()

        if not resp.data:
            return _load_stock_count_csv()

        df = pd.DataFrame(resp.data)
        df = df.rename(columns={"sku_id": "product_id", "on_hand_qty": "hoeveelheid"})
        return df[["product_id", "hoeveelheid"]].reset_index(drop=True)
    except Exception:
        return _load_stock_count_csv()


def _load_stock_count_csv() -> pd.DataFrame:
    """Fallback: laad standaard voorraad uit demo_data CSV."""
    pad = DEMO_DIR / "stock_count.csv"
    if not pad.exists():
        return pd.DataFrame(columns=["product_id", "hoeveelheid"])
    df = pd.read_csv(pad, parse_dates=["date"])
    df = df.rename(columns={"date": "datum", "sku_id": "product_id", "on_hand_qty": "hoeveelheid"})
    if df.empty:
        return pd.DataFrame(columns=["product_id", "hoeveelheid"])
    return df[df["datum"] == df["datum"].max()][["product_id", "hoeveelheid"]].reset_index(drop=True)


def sla_stock_op(datum: date, df_stock: pd.DataFrame) -> None:
    """
    Sla de closing-stock op in Supabase.
    df_stock verwacht kolommen: product_id, hoeveelheid.
    """
    rows = [
        {
            "date":        datum.isoformat(),
            "sku_id":      row["product_id"],
            "on_hand_qty": float(row["hoeveelheid"]),
            "unit":        "",
            "note":        "manager closing",
        }
        for _, row in df_stock.iterrows()
    ]
    db.get_client().table("stock_count").upsert(rows, on_conflict="date,sku_id").execute()


# ── E-mail ────────────────────────────────────────────────────────────────

def genereer_mailto(leverancier: str, df_lev: pd.DataFrame, bestel_datum: str) -> str:
    """
    Geeft een mailto: URL terug voor één leverancier.
    df_lev verwacht kolommen: naam, besteladvies, eenheid.
    """
    import urllib.parse

    cfg    = SUPPLIER_CONFIG.get(leverancier, {"email": "", "aanhef": "Beste leverancier,"})
    email  = cfg["email"]
    aanhef = cfg["aanhef"]

    onderwerp = f"Bestelling Family Maarssen — {leverancier} — {bestel_datum}"

    regels = "\n".join(
        f"  - {row['naam']}: {int(row['besteladvies'])} {row['eenheid']}"
        for _, row in df_lev.iterrows()
    )

    body = (
        f"{aanhef}\n\n"
        f"Hierbij onze bestelling voor levering op {bestel_datum}:\n\n"
        f"{regels}\n\n"
        f"Graag bevestiging van ontvangst.\n\n"
        f"Met vriendelijke groet,\n"
        f"Family Maarssen — Bisonspoor"
    )

    return f"mailto:{email}?subject={urllib.parse.quote(onderwerp)}&body={urllib.parse.quote(body)}"
