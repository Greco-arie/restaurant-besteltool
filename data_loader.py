"""Data loading + persistentie — normaliseert en slaat dagdata op."""
from pathlib import Path
from datetime import date
import pandas as pd

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


def load_products() -> pd.DataFrame:
    df = pd.read_csv(DEMO_DIR / "products.csv")
    # Normaliseer naar intern formaat
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


def load_sales_history() -> pd.DataFrame:
    df = pd.read_csv(DEMO_DIR / "sales_history.csv", parse_dates=["date"])
    df = df.rename(columns={
        "date":        "datum",
        "revenue_eur": "omzet",
    })
    # weekdag als getal (0=ma … 6=zo) — berekend uit datum (betrouwbaarder dan tekstkolom)
    df["weekdag"] = df["datum"].dt.day_of_week
    return df.sort_values("datum").reset_index(drop=True)


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


def sla_dag_op(
    datum:    date,
    covers:   int,
    omzet:    float,
    reserveringen: int = 0,
    notitie:  str  = "",
) -> None:
    """
    Sla de closing-data op in sales_history.csv.
    Overschrijft als de datum al bestaat (idempotent).
    """
    pad = DEMO_DIR / "sales_history.csv"
    df  = pd.read_csv(pad) if pad.exists() else pd.DataFrame(
        columns=["date","weekday","covers","revenue_eur","note"]
    )

    WEEKDAGEN_ENG = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    datum_str = datum.isoformat()
    weekday   = WEEKDAGEN_ENG[datum.weekday()]

    df = df[df["date"] != datum_str]  # verwijder bestaande rij voor deze datum
    nieuwe = pd.DataFrame([{
        "date":        datum_str,
        "weekday":     weekday,
        "covers":      covers,
        "revenue_eur": omzet,
        "note":        notitie,
    }])
    df = pd.concat([df, nieuwe], ignore_index=True)
    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(pad, index=False)


def sla_stock_op(datum: date, df_stock: pd.DataFrame) -> None:
    """
    Sla de closing-stock op in stock_count.csv.
    df_stock verwacht kolommen: product_id, hoeveelheid.
    Overschrijft bestaande rijen voor deze datum.
    """
    pad = DEMO_DIR / "stock_count.csv"
    df  = pd.read_csv(pad) if pad.exists() else pd.DataFrame(
        columns=["date","sku_id","on_hand_qty","unit","note"]
    )

    datum_str = datum.isoformat()
    df = df[df["date"] != datum_str]

    nieuwe = df_stock[["product_id","hoeveelheid"]].copy()
    nieuwe.columns = ["sku_id","on_hand_qty"]
    nieuwe["date"] = datum_str
    nieuwe["unit"] = ""
    nieuwe["note"] = "manager closing"
    nieuwe = nieuwe[["date","sku_id","on_hand_qty","unit","note"]]

    df = pd.concat([df, nieuwe], ignore_index=True)
    df = df.sort_values(["date","sku_id"]).reset_index(drop=True)
    df.to_csv(pad, index=False)


def genereer_mailto(leverancier: str, df_lev: pd.DataFrame, bestel_datum: str) -> str:
    """
    Geeft een mailto: URL terug voor één leverancier.
    df_lev verwacht kolommen: naam, besteladvies, eenheid.
    bestel_datum: YYYY-MM-DD string van de leverdag.
    """
    import urllib.parse

    cfg     = SUPPLIER_CONFIG.get(leverancier, {"email": "", "aanhef": "Beste leverancier,"})
    email   = cfg["email"]
    aanhef  = cfg["aanhef"]

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


def load_stock_count(datum_str: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(DEMO_DIR / "stock_count.csv", parse_dates=["date"])
    df = df.rename(columns={
        "date":       "datum",
        "sku_id":     "product_id",
        "on_hand_qty":"hoeveelheid",
    })
    if datum_str:
        filtered = df[df["datum"] == datum_str]
        if not filtered.empty:
            return filtered.reset_index(drop=True)
    return df[df["datum"] == df["datum"].max()].reset_index(drop=True)
