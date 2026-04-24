# RLS Policies — Restaurant Besteltool V2

> **Fase 3.1 — tenant-isolatie via Postgres Row-Level Security + JWT**
> Migraties: `supabase_migration_v12_rls_jwt_policies.sql` en `supabase_migration_v13_audit_log.sql`
> Tests: `tests/test_rls.py`

---

## TL;DR

Er zijn **twee paden** naar Supabase. Kies bewust welke je gebruikt:

| Helper | Gebruikt | Bypassed RLS? | Wanneer |
|---|---|---|---|
| `get_tenant_client(tenant_id)` | `anon_key` + gesigned JWT | **nee** — Postgres handhaaft | **Standaard** voor alle tenant-data |
| `get_admin_client()` | `service_role` key | **ja** — bypassed volledig | Alleen super_admin + audit INSERT |
| `get_client()` | idem als admin (legacy) | ja | **DEPRECATED** — gefaseerde migratie naar bovenstaande twee |

## Architectuur

```
Streamlit app
     │
     │ (1) gebruiker logt in → UserSession met tenant_id
     │
     ▼
 db.py keuze:
 ┌───────────────────────────────────┐   ┌──────────────────────────────┐
 │ get_tenant_client(tenant_id)      │   │ get_admin_client()           │
 │  - anon_key (publiek)             │   │  - service_role key (geheim) │
 │  - pyjwt.encode({tenant_id, ...}) │   │  - geen JWT                  │
 │  - 1u geldig, NIET gecached       │   │  - @st.cache_resource        │
 └────────────┬──────────────────────┘   └──────────────┬───────────────┘
              │ Authorization: Bearer <JWT>             │ apikey: <service_role>
              ▼                                         ▼
 Supabase PostgREST / Postgres
  auth.jwt() ->> 'tenant_id'                     service_role → bypass
              │                                         │
              ▼                                         ▼
 RLS-policy: tenant_isolation (v12)              geen check, alle rijen
  tenant_id = tenant_jwt_id()
```

### JWT-pad (tenant-scoped)

- App signt HS256 JWT met claims: `role=authenticated`, `tenant_id=<uuid>`, `iss=supabase`, `exp=iat+3600`.
- Supabase valideert JWT met dezelfde `jwt_secret` (staat in project settings).
- Policy `tenant_isolation` op elke tenant-tabel leest `tenant_jwt_id()` (hulpfunctie uit v12) en vergelijkt met rij.`tenant_id`.
- Geldigheid: **1 uur**. Niet gecached; elke call genereert verse JWT zodat expiry nooit bijt.

### Service-role-pad (admin)

- `service_role` key is een vooraf gegenereerde key die **alle RLS policies automatisch bypassed**.
- Vereist dus maximale zorgvuldigheid: elke call potentieel cross-tenant.
- Mag alleen in super_admin-flows en in specifieke gevallen (audit INSERT).

## Policy-overzicht

### Tabellen MÉT RLS (tenant-scoped — gebruik `get_tenant_client`)

| Tabel | Policy | CMD / Role | Bron | Rationale |
|---|---|---|---|---|
| `suppliers` | `tenant_isolation` | `ALL / authenticated` | v12 | Leveranciers per tenant geïsoleerd |
| `products` | `tenant_isolation` | `ALL / authenticated` | v12 | Productlijst per tenant geïsoleerd |
| `sent_emails` | `tenant_isolation` | `ALL / authenticated` | v12 | Verzendhistorie per tenant |
| `sales_history` | `tenant_isolation` | `ALL / authenticated` | v12 | Closings — bedrijfsgevoelig |
| `stock_count` | `tenant_isolation` | `ALL / authenticated` | v12 | Voorraadtellingen |
| `forecast_log` | `tenant_isolation` | `ALL / authenticated` | v12 | Forecast-geschiedenis (learning) |
| `current_inventory` | `tenant_isolation` | `ALL / authenticated` | v12 | Live voorraad |
| `inventory_adjustments` | `tenant_isolation` | `ALL / authenticated` | v12 | Correcties (breuk, verbruik) |
| `daily_usage` | `tenant_isolation` | `ALL / authenticated` | v12 | Dagelijks verbruik |
| `audit_log` | `tenant_isolation_read` | `SELECT / authenticated` | v13 | Lees via JWT, **schrijf altijd via service_role** |

### Tabellen ZONDER RLS (admin-only — gebruik `get_admin_client`)

| Tabel | Rationale |
|---|---|
| `tenants` | Alleen super_admin beheert tenants |
| `tenant_users` | Idem — gebruikersbeheer is admin-scoped |
| `password_reset_tokens` | Moet cross-tenant op e-mail kunnen zoeken |

## Beslisschema voor callers

```
Query raakt een rij met tenant_id kolom?
  ├── Ja → gebruik get_tenant_client(tenant_id)   # RLS afgedwongen
  └── Nee (tenants / tenant_users / reset_tokens) → get_admin_client()

Uitzondering: audit_log INSERT
  → altijd get_admin_client() (RLS blokkeert INSERT voor authenticated)
```

## DO

```python
# Tenant-scoped read (correct — RLS afgedwongen)
from db import get_tenant_client
producten = get_tenant_client(session.tenant_id).table("products").select("*").execute()

# Super_admin tenant-beheer (correct — cross-tenant nodig)
from db import get_admin_client
tenants = get_admin_client().table("tenants").select("*").execute()

# Audit log INSERT (correct — RLS blokkeert INSERT voor authenticated)
get_admin_client().table("audit_log").insert({
    "tenant_id": tenant_id, "user_naam": user, "actie": "login",
}).execute()
```

## DON'T

```python
# FOUT: tenant-data via admin-client bypasst RLS
# → latent security-gat, werkt vandaag, faalt zodra RLS strakker wordt
get_admin_client().table("sales_history").select("*").execute()

# FOUT: tenants / tenant_users hebben geen authenticated-policy
# → 0 rijen, gebruiker denkt dat er geen data is
get_tenant_client(tenant_id).table("tenants").select("*").execute()

# FOUT: JWT cachen betekent expired tokens na 1u
@st.cache_resource
def haal_tenant_client():
    return get_tenant_client(tenant_id)  # NIET DOEN
```

## Tests

`tests/test_rls.py` levert twee lagen bewijs:

### Unit (altijd aan — `pytest -m unit`)
- JWT bevat correcte claims (role, tenant_id, iss, sub)
- JWT exp ≈ iat + 3600 (1 uur geldigheid)
- Twee calls met zelfde tenant_id geven twee verschillende JWTs (niet gecached)

### Integration (opt-in — `RLS_TEST_ENABLED=1 pytest -m integration`)
- Cliënt A ziet geen suppliers van tenant B
- Cliënt A ziet wel z'n eigen suppliers
- JWT zonder `tenant_id` claim → 0 rijen
- Parametrized over alle 9 tenant-tabellen — RLS werkt op elk

### Integration tests runnen (lokaal)

1. Kopieer `.env.example` → `.env.test` (in projectroot, NIET committen)
2. Vul in:
   ```
   SUPABASE_URL=https://<jouw-project>.supabase.co
   SUPABASE_ANON_KEY=<anon key uit Supabase Settings → API>
   SUPABASE_SERVICE_KEY=<service_role key>
   SUPABASE_JWT_SECRET=<JWT secret uit Settings → API>
   ```
3. Run:
   ```bash
   RLS_TEST_ENABLED=1 pytest -m integration -v
   ```

De integration-fixture maakt zelf twee test-tenants aan (`rls_test_alpha_*`, `rls_test_beta_*`), seedt één supplier per tenant, en ruimt alles op na afloop via `try/finally`.

## Verificatie in Supabase

Controleer policies via SQL Editor:

```sql
SELECT schemaname, tablename, policyname, cmd, roles
FROM   pg_policies
WHERE  policyname LIKE 'tenant_isolation%'
ORDER  BY tablename;
```

Verwacht: **10 rijen** (9 × `tenant_isolation` + 1 × `tenant_isolation_read` op audit_log).

## Migratiestatus van callers

**Status 2026-04-24**: `get_tenant_client` wordt correct gebruikt in een deel van `db.py`
(suppliers, products, sent_emails). Veel andere callers in `data_loader.py`,
`inventory.py`, `learning.py`, en `views/*.py` gebruiken nog `get_client()` (=service_role)
voor tenant-data. Dat werkt vandaag (service_role bypasst RLS) maar is een latent risico
en ondergraaft de isolatie-doelstelling.

**Follow-up (Stap 1b)**: Per module migreren naar `get_admin_client` (admin) of
`get_tenant_client(tenant_id)` (tenant-data). Aparte PR, per module review.

## Referentie

- Migratie v12: `supabase_migration_v12_rls_jwt_policies.sql`
- Migratie v13: `supabase_migration_v13_audit_log.sql`
- Code: `db.py` → `get_admin_client`, `get_tenant_client`
- Tests: `tests/test_rls.py` + `tests/conftest.py`
