"""
Migreer products.csv naar Supabase products tabel.

Gebruik:
  python migrate_products.py --tenant-slug family-maarssen
  python migrate_products.py --tenant-slug family-maarssen --dry-run

Vlaggen:
  --tenant-slug   Slug van de tenant (verplicht)
  --dry-run       Toon diff zonder iets op te slaan
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────

DEMO_CSV = Path(__file__).parent / "demo_data" / "products.csv"

SUPPLIER_NAMEN: dict[str, str] = {
    "wholesale": "Hanos",
    "fresh":     "Vers Leverancier",
    "bakery":    "Bakkersland",
    "beer":      "Heineken Distrib.",
}


# ── Supabase verbinding (leest .streamlit/secrets.toml) ───────────────────

def _get_client():
    try:
        import toml
        secrets = toml.load(Path(__file__).parent / ".streamlit" / "secrets.toml")
        url = secrets["supabase"]["url"]
        key = secrets["supabase"]["service_key"]
    except Exception as e:
        print(f"[FOUT] Kan secrets niet laden: {e}")
        sys.exit(1)
    return create_client(url, key)


# ── Helpers ───────────────────────────────────────────────────────────────

def _laad_tenant_id(sb, slug: str) -> str:
    resp = sb.table("tenants").select("id").eq("slug", slug).single().execute()
    if not resp.data:
        print(f"[FOUT] Tenant '{slug}' niet gevonden.")
        sys.exit(1)
    return resp.data["id"]


def _laad_suppliers(sb, tenant_id: str) -> dict[str, str]:
    """Geeft naam → supplier_id dict voor de tenant."""
    resp = sb.table("suppliers").select("id, name").eq("tenant_id", tenant_id).execute()
    return {r["name"]: r["id"] for r in (resp.data or [])}


def _laad_bestaande_skus(sb, tenant_id: str) -> dict[str, dict]:
    """Geeft sku_id → product-rij dict voor de tenant."""
    resp = (
        sb.table("products")
        .select("sku_id, naam, eenheid, verpakkingseenheid, vraag_per_cover, minimumvoorraad, buffer_pct")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    return {r["sku_id"]: r for r in (resp.data or [])}


def _is_gewijzigd(bestaand: dict, nieuw: dict) -> bool:
    tekst_velden    = ["naam", "eenheid"]
    numeriek_velden = ["verpakkingseenheid", "vraag_per_cover", "minimumvoorraad", "buffer_pct"]
    for v in tekst_velden:
        if str(bestaand.get(v, "")) != str(nieuw.get(v, "")):
            return True
    for v in numeriek_velden:
        if abs(float(bestaand.get(v, 0) or 0) - float(nieuw.get(v, 0) or 0)) > 1e-6:
            return True
    return False


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Migreer products.csv → Supabase")
    parser.add_argument("--tenant-slug", required=True, help="Slug van de tenant")
    parser.add_argument("--dry-run", action="store_true", help="Toon diff, sla niets op")
    args = parser.parse_args()

    if not DEMO_CSV.exists():
        print(f"[FOUT] CSV niet gevonden: {DEMO_CSV}")
        sys.exit(1)

    sb        = _get_client()
    tenant_id = _laad_tenant_id(sb, args.tenant_slug)
    suppliers = _laad_suppliers(sb, tenant_id)
    bestaand  = _laad_bestaande_skus(sb, tenant_id)

    df = pd.read_csv(DEMO_CSV)

    nieuw_count      = 0
    gewijzigd_count  = 0
    ongewijzigd_count = 0
    fouten: list[str] = []

    print(f"\nTenant : {args.tenant_slug} ({tenant_id})")
    print(f"CSV    : {len(df)} producten")
    print(f"Modus  : {'DRY-RUN' if args.dry_run else 'LIVE'}\n")

    upsert_rows: list[dict] = []

    for _, row in df.iterrows():
        sku_id       = str(row["sku_id"]).strip().upper()
        supplier_type = str(row.get("supplier_type", "")).strip()
        supplier_naam = SUPPLIER_NAMEN.get(supplier_type, "Overig")
        supplier_id   = suppliers.get(supplier_naam)

        if supplier_id is None and supplier_naam != "Overig":
            fouten.append(
                f"  [WAARSCHUWING] {sku_id}: leverancier '{supplier_naam}' niet gevonden in DB "
                f"(supplier_type='{supplier_type}'). supplier_id blijft NULL."
            )

        nieuw_record: dict = {
            "tenant_id":          tenant_id,
            "sku_id":             sku_id,
            "naam":               str(row["sku_name"]).strip(),
            "eenheid":            str(row["base_unit"]).strip(),
            "verpakkingseenheid": float(row["pack_qty"]),
            "vraag_per_cover":    float(row["demand_per_cover"]),
            "minimumvoorraad":    float(row.get("min_stock", 0) or 0),
            "buffer_pct":         float(row.get("buffer_pct", 0.15) or 0.15),
            "supplier_id":        supplier_id,
            "is_actief":          True,
        }

        if sku_id not in bestaand:
            nieuw_count += 1
            status = "NIEUW    "
        elif _is_gewijzigd(bestaand[sku_id], nieuw_record):
            gewijzigd_count += 1
            status = "GEWIJZIGD"
        else:
            ongewijzigd_count += 1
            status = "—        "

        print(f"  {status} {sku_id:10s} {nieuw_record['naam'][:40]:<40s} [{supplier_naam}]")
        upsert_rows.append(nieuw_record)

    print(f"\nResultaat: {nieuw_count} nieuw · {gewijzigd_count} gewijzigd · {ongewijzigd_count} ongewijzigd")

    if fouten:
        print("\nWaarschuwingen:")
        for f in fouten:
            print(f)

    if args.dry_run:
        print("\n[DRY-RUN] Niets opgeslagen.")
        return

    print("\nOpslaan naar Supabase...")
    try:
        sb.table("products").upsert(upsert_rows, on_conflict="tenant_id,sku_id").execute()
        print(f"[OK] {len(upsert_rows)} producten geüpsert.")
    except Exception as e:
        print(f"[FOUT] Upsert mislukt: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
