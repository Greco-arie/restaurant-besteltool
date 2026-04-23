-- Migration v10: products tabel
-- Voer uit in Supabase SQL Editor (Dashboard → SQL Editor → New query)

CREATE TABLE IF NOT EXISTS products (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sku_id              TEXT NOT NULL,
    naam                TEXT NOT NULL,
    eenheid             TEXT NOT NULL,
    verpakkingseenheid  NUMERIC NOT NULL DEFAULT 1,
    vraag_per_cover     NUMERIC NOT NULL DEFAULT 0,
    minimumvoorraad     NUMERIC NOT NULL DEFAULT 0,
    buffer_pct          NUMERIC NOT NULL DEFAULT 0.15,
    supplier_id         UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    cost_price          NUMERIC(10,4),
    is_actief           BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(tenant_id, sku_id)
);

ALTER TABLE products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_producten_isolatie" ON products
    USING (tenant_id::text = auth.jwt() ->> 'tenant_id');

-- Index voor snelle tenant-queries
CREATE INDEX IF NOT EXISTS idx_products_tenant_id ON products(tenant_id);
CREATE INDEX IF NOT EXISTS idx_products_tenant_sku ON products(tenant_id, sku_id);
