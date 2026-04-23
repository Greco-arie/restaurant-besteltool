# FASE 11 — UX + ONBOARDING
# Vereiste: Fase 2 (products-tabel). Fase 7 aanbevolen voor CSV-import.
# Plak dit samen met BASE_CONTEXT.md.

──────────────────────────────────────────────────────────────
[F11.1] TABLET-GEOPTIMALISEERDE REVIEW-PAGINA
──────────────────────────────────────────────────────────────
Pas views/page_review.py aan — NIET herbouwen.
Houd bestaand CSS-designsysteem (Ink Indigo #2E5AAC) uit app.py.

Toevoegingen:
  - Grote knoppen (min 48×48px touch target)
  - +/- knoppen per product (hoeveelheid aanpassen)
  - Accordeon per leverancier (standaard ingeklapt)
  - Minimale scroll op 768px viewport

──────────────────────────────────────────────────────────────
[F11.2] STARTERSCATALOGI + VOORGEDEFINIEERDE LEVERANCIERS
──────────────────────────────────────────────────────────────
SQL (supabase_seed_katalogi.sql):
  CREATE TABLE starter_catalogs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kitchen_type  TEXT NOT NULL,  -- italiaans/aziatisch/bistro/brasserie/grill/cafe
    product_template JSONB NOT NULL
  );
  Seed: 30–50 producten per keukentype.

Seed leveranciers (supabase_seed_leveranciers.sql):
  Hanos, Sligro, Bidfood, Makro, Lekkerland met standaard leverdagen (ma–vr).

Pas views/page_instellingen.py aan:
  Bij onboarding: keukentype kiezen + leveranciers uit preset-lijst.
  Eigen leveranciers toevoegen blijft mogelijk.

──────────────────────────────────────────────────────────────
[F11.3] EXCEL/CSV-IMPORT WIZARD
──────────────────────────────────────────────────────────────
Voeg sectie toe aan views/page_producten.py (bestaande pagina).

Upload .xlsx of .csv:
  1. Kolom-mapping (welke kolom is sku_id, naam, etc.)
  2. Preview: eerste 10 rijen
  3. Import met duplicate-detectie op (tenant_id, sku_id)
  4. Rapport: X geïmporteerd · Y gewijzigd · Z overgeslagen (duplicaat)

Libraries: openpyxl (voor .xlsx) · csv (stdlib, voor .csv).
