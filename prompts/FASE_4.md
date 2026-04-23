# FASE 4 — RECEPTENBEHEER
# Vereiste: Fase 2 (products-tabel in Supabase).
# Toegang: manager, admin, super_admin.
# Plak dit samen met BASE_CONTEXT.md.

PROBLEEM: vraag_per_cover is handmatig ingesteld en raakt verouderd bij portiewijziging.
OPLOSSING: recepten koppelen aan producten; elke wijziging herberekent vraag_per_cover auto.

──────────────────────────────────────────────────────────────
[F4.1] DATABASE
──────────────────────────────────────────────────────────────
supabase_migration_v12_recepten.sql:

  CREATE TABLE recipes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    naam          TEXT NOT NULL,
    selling_price NUMERIC(10,2),
    beschrijving  TEXT,
    is_actief     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  RLS policy op tenant_id.

  CREATE TABLE recipe_ingredients (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id            UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    product_id           UUID NOT NULL REFERENCES products(id),
    quantity_per_serving NUMERIC NOT NULL,
    unit                 TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(recipe_id, product_id)
  );
  RLS: join via recipes.tenant_id.

──────────────────────────────────────────────────────────────
[F4.2] LOGICA (db.py uitbreiden)
──────────────────────────────────────────────────────────────
laad_recepten(tenant_id) → list[dict]
sla_recept_op(tenant_id, recept_data, ingrediënten) → UUID
herbereken_vraag_per_cover(tenant_id, product_id) → float
  Som van quantity_per_serving × (gerecht_covers_per_dag / totale_covers) over alle actieve recepten
  Schrijf resultaat terug naar products.vraag_per_cover
  Log in inventory_adjustments: reason='recept_wijziging',
    note=f"Recept '{naam}' gewijzigd: portie {oud} → {nieuw}"
  Invalideer st.cache_data voor producten

──────────────────────────────────────────────────────────────
[F4.3] MODELS (models.py uitbreiden)
──────────────────────────────────────────────────────────────
class Recipe(BaseModel, frozen=True):
    id: UUID; tenant_id: UUID; naam: str
    selling_price: Decimal | None; beschrijving: str | None; is_actief: bool

class RecipeIngredient(BaseModel, frozen=True):
    id: UUID; recipe_id: UUID; product_id: UUID
    quantity_per_serving: Decimal; unit: str

──────────────────────────────────────────────────────────────
[F4.4] UI (views/page_recepten.py — nieuw bestand)
──────────────────────────────────────────────────────────────
Sectie 1 — Overzicht:
  Tabel: naam, verkoopprijs, aantal ingrediënten, actief/inactief

Sectie 2 — Toevoegen/bewerken:
  Formulier: naam, verkoopprijs, beschrijving
  Ingrediënten-editor: per regel → product (dropdown), hoeveelheid, eenheid
  Nieuw product toevoegen → link naar page_producten.py

Sectie 3 — Impact-preview (VOOR opslaan tonen):
  "Dit wijzigt vraag_per_cover van [product X] van 0.08 naar 0.11"
  "Dit beïnvloedt het besteladvies."
  Manager bevestigt expliciet → dan pas opslaan + herberekening.

Voeg "Recepten" toe aan navigatie in app.py voor rollen >= manager.
