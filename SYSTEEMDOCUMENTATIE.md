# Restaurant Besteltool — Volledige Systeemdocumentatie

**Versie:** 1.0  
**Datum:** April 2026  
**Project:** Restaurant Forecast & Besteladvies  
**Platform:** Streamlit Cloud  
**Database:** Supabase (PostgreSQL)

---

## Inhoudsopgave

1. [Wat is de besteltool?](#1-wat-is-de-besteltool)
2. [Tijdsbesparing voor de manager](#2-tijdsbesparing-voor-de-manager)
3. [Architectuuroverzicht](#3-architectuuroverzicht)
4. [Datastromen — compleet overzicht](#4-datastromen--compleet-overzicht)
5. [API-verbindingen](#5-api-verbindingen)
6. [Dagelijkse werkinstructie](#6-dagelijkse-werkinstructie)
7. [Wat de manager bijhoudt](#7-wat-de-manager-bijhoudt)
8. [Wat het systeem automatisch overneemt](#8-wat-het-systeem-automatisch-overneemt)
9. [Inventarisbeheer — hoe het werkt](#9-inventarisbeheer--hoe-het-werkt)
10. [Het lerende systeem](#10-het-lerende-systeem)
11. [Gebruikers en toegangsniveaus](#11-gebruikers-en-toegangsniveaus)
12. [Multi-tenant architectuur](#12-multi-tenant-architectuur)
13. [Databasetabellen](#13-databasetabellen)
14. [Codestructuur](#14-codestructuur)
15. [Beveiliging](#15-beveiliging)

---

## 1. Wat is de besteltool?

De Restaurant Besteltool is een webapplicatie die een horecamanager helpt bij het dagelijks afsluiten van de dag, het berekenen van een inkoop-forecast voor morgen, en het genereren van een kant-en-klare bestellijst per leverancier.

Het systeem combineert:
- Historische verkoopdata (hoeveel bonnen/omzet)
- Weersverwachting voor morgen (via Open-Meteo API)
- Actuele voorraadstanden
- Geplande evenementen en reserveringen
- Een zelflerend correctiemodel per weekdag

Het eindresultaat is een automatisch gegenereerde bestellijst, gesplitst per leverancier, die direct als e-mail verstuurd of als CSV-bestand gedownload kan worden.

---

## 2. Tijdsbesparing voor de manager

### Situatie zonder de tool

Elke dag moet een manager handmatig:
- Bepalen hoeveel gasten er morgen komen (giswerk op basis van ervaring)
- Uitrekenen hoeveel van elk product nodig is (×60 bonnen = hoeveel kg friet?)
- Controleren wat er nog op voorraad ligt
- Een bestellijst opstellen per leverancier
- Die lijst via e-mail of telefoon doorbellen

Dit kost gemiddeld **45–90 minuten per dag**, afhankelijk van ervaring.

### Situatie met de tool

De manager:
1. Vult 3 velden in (bonnen vandaag, omzet, sluitstock)
2. Klikt op "Bereken"
3. Controleert de automatisch gegenereerde bestellijst
4. Klikt op "Verstuur naar leverancier"

Dit kost gemiddeld **8–15 minuten per dag**.

### Concrete tijdsbesparing

| Taak | Zonder tool | Met tool |
|------|-------------|----------|
| Forecast bepalen | 15–25 min | Automatisch |
| Besteladvies berekenen | 20–30 min | Automatisch |
| Bestellijst opstellen | 10–20 min | Automatisch |
| E-mail schrijven per leverancier | 5–15 min per lev. | 1 klik |
| **Totaal** | **45–90 min/dag** | **8–15 min/dag** |

**Geschatte besparing:** ~1 uur per dag = ~250 uur per jaar = significante loonkostenbesparing.

### Nauwkeurigheidsvoordelen

Naast tijdsbesparing vermindert het systeem menselijke fouten:
- Geen vergeten bufferhoeveelheden
- Geen verkeerde omrekening (kg → stuks)
- Geen bestellijst die gebaseerd is op een te optimistische of pessimistische schatting
- Automatische correctie als het systeem structureel te hoog of te laag voorspelt

---

## 3. Architectuuroverzicht

```
┌─────────────────────────────────────────────────────────────────┐
│                     STREAMLIT CLOUD                             │
│                                                                 │
│  app.py          → hoofd UI + navigatie                        │
│  forecast.py     → forecastengine                              │
│  recommendation.py → besteladvies berekeningen                 │
│  inventory.py    → voorraad lezen/schrijven                    │
│  learning.py     → leermodel (correctiefactoren)               │
│  data_loader.py  → data lezen/schrijven naar Supabase          │
│  weather.py      → weer ophalen via API                        │
│  db.py           → Supabase client + auth helpers              │
└─────────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐       ┌──────────────────────────┐
│  SUPABASE           │       │  OPEN-METEO API           │
│  (PostgreSQL)       │       │  api.open-meteo.com       │
│                     │       │                           │
│  - tenants          │       │  - Geen API-key nodig     │
│  - tenant_users     │       │  - Dagelijkse forecast    │
│  - sales_history    │       │  - Coördinaten Maarssen   │
│  - forecast_log     │       │    LAT 52.1367            │
│  - current_inventory│       │    LON 5.0378             │
│  - inventory_adj.   │       │                           │
│  - daily_usage      │       └──────────────────────────┘
│  - stock_count      │
└─────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  LOKALE DEMO DATA (CSV)     │
│  demo_data/                 │
│  - products.csv (30 SKUs)   │
│  - events.csv               │
│  - reservations.csv         │
│  - sales_history.csv        │
└─────────────────────────────┘
```

---

## 4. Datastromen — compleet overzicht

### Datastroom 1: Dag afsluiten (invoer → opslaan)

```
Manager vult in:
  ├── Datum (automatisch vandaag)
  ├── Bonnen vandaag (integer)
  ├── Omzet vandaag (€)
  ├── Reserveringen morgen
  ├── Party platters 25/50 stuks
  ├── Bijzonderheden (vrije tekst)
  └── Sluitstock per artikel (data editor)
           │
           ▼
data_loader.sla_dag_op()
  → INSERT/UPSERT naar sales_history
  → Kolommen: tenant_id, date, weekday, covers, revenue_eur, note
           │
           ▼
data_loader.sla_stock_op()
  → INSERT/UPSERT naar stock_count
  → Kolommen: tenant_id, date, sku_id, on_hand_qty, unit
           │
           ▼
inventory.sla_sluitstock_op()
  → UPSERT naar current_inventory (live stand)
  → INSERT naar inventory_adjustments (audit trail)
           │
           ▼
inventory.log_theoretisch_verbruik()
  → UPSERT naar daily_usage
  → Berekend: vraag_per_cover × actual_covers per SKU
```

### Datastroom 2: Forecast berekenen

```
data_loader.load_sales_history(tenant_id)
  └── SELECT sales_history WHERE tenant_id = X
           │
           ▼
forecast.bereken_baseline()
  └── Gemiddelde covers van laatste 4 gelijke weekdagen
           │
forecast.bereken_trend()
  └── Verhouding laatste 14 dagen vs. vorige 14 dagen
           │
forecast.bereken_event_factors()
  └── Lees events.csv: is er een event morgen?
      Geeft covers_mult, fries_mult, desserts_mult
           │
weather.get_weer_morgen()
  └── HTTP GET → api.open-meteo.com
      Geeft temp_max, precip_prob, terras_factor, drinks_factor
           │
learning.bereken_correctiefactor(tenant_id, weekdag)
  └── SELECT forecast_log WHERE tenant_id = X AND weekdag = Y
      Berekent ratio actual/predicted over laatste 8 voltooide dagen
           │
           ▼
Eindformule:
  forecast_covers = baseline
                  × trend_factor
                  × reserveringscorrectie
                  × event_covers_multiplier
                  × correctie_factor
                  × terras_factor
           │
           ▼
learning.log_forecast()
  → INSERT/UPSERT naar forecast_log
  → Kolommen: tenant_id, datum, weekdag, predicted_covers, event_naam, notitie
```

### Datastroom 3: Besteladvies berekenen

```
recommendation.bereken_alle_adviezen()
  │
  ├── Input: 30 producten uit products.csv
  ├── Input: forecast_covers (int)
  ├── Input: huidige voorraad per SKU (data editor of Supabase)
  ├── Input: event multipliers
  └── Input: party platter aantallen
           │
           ▼
Per product (30 SKUs):
  verwachte_vraag  = vraag_per_cover × forecast_covers × multipliers
  buffer_qty       = verwachte_vraag × buffer_pct
  platter_extra    = (platters_25 × extra_25) + (platters_50 × extra_50)
  bruto_behoefte   = verwachte_vraag + buffer_qty + platter_extra − voorraad
  besteladvies     = afgerond_op_verpakking(bruto_behoefte) als > 0, anders 0
           │
           ▼
Groepering per leverancier:
  - Hanos (wholesale: 21 SKUs)
  - Vers Leverancier (fresh: 7 SKUs)
  - Bakkersland (bakery: 1 SKU)
  - Heineken Distrib. (beer: 1 SKU)
```

### Datastroom 4: Export & bestelling versturen

```
Goedgekeurde bestellijst per leverancier
  │
  ├── E-mail knop:
  │     data_loader.genereer_mailto()
  │     → Bouwt mailto: URL met onderwerp + bestellijst in body
  │     → Opent standaard e-mailclient van de manager
  │
  └── CSV download knop:
        → browser download van bestelling_DATUM_LEVERANCIER.csv
```

### Datastroom 5: Leermodel — werkelijk invullen

```
Volgende dag: manager vult werkelijke bonnen in op sluitscherm
  │
  ▼
learning.log_werkelijk(tenant_id, datum, actual_covers, omzet)
  → UPDATE forecast_log SET actual_covers = X WHERE datum = Y AND tenant_id = Z
  │
  ▼
learning.bereken_correctiefactor() (volgende keer dat forecast wordt berekend)
  → Leest laatste 8 voltooide rijen per weekdag
  → factor = gemiddelde(actual / predicted)
  → Begrensd op 0.75 – 1.30 (systeem kan maximaal 30% bijsturen)
  → Wordt automatisch toegepast op volgende forecast voor die weekdag
```

---

## 5. API-verbindingen

### 5.1 Supabase (database + authenticatie)

**Type:** REST API via Python client  
**Library:** `supabase-py` (versie ≥ 2.x)  
**Authenticatie:** Service Role Key (volledige lees/schrijftoegang)

**Configuratie** (in `.streamlit/secrets.toml`, nooit in code):
```toml
[supabase]
url = "https://PROJECTID.supabase.co"
key = "eyJhbG..."   # service_role key
```

**Hoe het werkt:**
- `db.get_client()` maakt één gecachte Supabase client aan per Streamlit-sessie
- Alle queries gaan via de Supabase PostgREST API (HTTPS)
- Elke tabel-operatie is een HTTP-aanroep: GET (SELECT), POST (INSERT), PATCH (UPDATE)
- De client is gecached via `@st.cache_resource` — wordt niet bij elke page-refresh opnieuw aangemaakt

**Gebruikte operaties:**
| Operatie | Python | SQL equivalent |
|----------|--------|----------------|
| Lezen | `.select("*").eq("tenant_id", x)` | `SELECT * WHERE tenant_id = x` |
| Schrijven | `.insert({...})` | `INSERT INTO ...` |
| Upsert | `.upsert({...}, on_conflict="...")` | `INSERT ... ON CONFLICT DO UPDATE` |
| Updaten | `.update({...}).eq("datum", x)` | `UPDATE ... WHERE datum = x` |

**Row Level Security (RLS):** Uitgeschakeld — toegangscontrole verloopt via de applicatielaag (inlogcheck in app.py) en de service role key.

---

### 5.2 Open-Meteo (weersvoorspelling)

**Type:** Publieke REST API  
**URL:** `https://api.open-meteo.com/v1/forecast`  
**Authenticatie:** Geen API-key vereist (gratis, open gebruik)  
**Library:** Standaard `urllib.request` (geen externe dependency)

**Request voorbeeld:**
```
GET https://api.open-meteo.com/v1/forecast
  ?latitude=52.1367
  &longitude=5.0378
  &daily=temperature_2m_max,precipitation_probability_max,weathercode
  &timezone=Europe%2FAmsterdam
  &forecast_days=3
```

**Locatie:** Maarssen, Bisonspoor (Utrecht-regio)  
Coördinaten: `LAT 52.1367`, `LON 5.0378`

**Wat wordt opgehaald:**
| Veld | Betekenis |
|------|-----------|
| `temperature_2m_max` | Maximale temperatuur op 2m hoogte (°C) |
| `precipitation_probability_max` | Maximale regenkansprognose (%) |
| `weathercode` | WMO-weercode (internationaal standaard) |

**Terraslogica:**

| Conditie | terras_factor | drinks_factor | Effect |
|----------|--------------|---------------|--------|
| ≥20°C + ≤30% regenrisico | ×1.40 | ×1.60 | Terras vol verwacht |
| ≥15°C + ≤59% regenrisico | ×1.18 | ×1.30 | Terras gedeeltelijk open |
| <15°C of regen (≥60%) | ×1.00 | ×1.00 | Terras dicht |

**Caching:** Via `@lru_cache(maxsize=1)` — de API wordt maximaal 1× per Streamlit-sessie aangeroepen. Bij herstart van de app wordt de cache geleegd.

**Fallback:** Als de API niet bereikbaar is (timeout 5 seconden), worden `terras_factor = 1.0` en `drinks_factor = 1.0` gebruikt. De forecast wordt dan berekend zonder weercorrectie.

---

### 5.3 GitHub (deployment pipeline)

**Type:** Git remote  
**Repo:** `Greco-arie/restaurant-besteltool` (privé)  
**Gebruik:** Streamlit Cloud haalt de code automatisch op bij elke push naar `main`

**Deploy flow:**
```
Lokale wijziging in code
    │
    ▼
git push origin main
    │
    ▼
Streamlit Cloud detecteert nieuwe commit
    │
    ▼
Container herstart automatisch
    │
    ▼
Nieuwe versie live (binnen ~60 seconden)
```

---

## 6. Dagelijkse werkinstructie

### Tijdstip: Aan het einde van elke werkdag (bij afsluiting)

**Stap 1 — Dag afsluiten (pagina: "Dag afsluiten")**

Vul in:
- **Datum:** Automatisch ingevuld op vandaag
- **Bonnen vandaag:** Het totaal aantal transacties/orders van vandaag
- **Omzet vandaag (€):** De totale dagomzet
- **Reserveringen morgen:** Hoeveel vaste covers er al vastliggen voor morgen
- **Partycatering 25/50 st:** Alleen invullen als er een party-platter bestelling is
- **Bijzonderheden:** Korte notitie (bv. "terras open gehad", "markt in de buurt", "concert in centrum")
- **Sluitstock:** Tel elk kritiek artikel door en vul de hoeveelheid in

> **Tip over bijzonderheden:** Schrijf elke dag een korte, consistente notitie. Na 2 keer dezelfde notitie berekent het systeem automatisch of die situatie historisch voor meer of minder bonnen zorgde.

**Stap 2 — Forecast controleren (pagina: "Forecast")**

Het systeem toont:
- Verwacht aantal bonnen voor morgen
- Verwachte omzet
- Betrouwbaarheidscore (Hoog/Gemiddeld/Laag)
- Alle factoren die de forecast beïnvloed hebben

Controleer of de forecast klopt. Zijn er omstandigheden die het systeem niet kan weten? Ga terug en pas de bijzonderheden aan.

**Stap 3 — Besteladvies controleren (pagina: "Bestelreview")**

Het systeem toont per product:
- Huidige voorraad
- Verwachte vraag
- Buffer
- Besteladvies (hoeveel te bestellen)

Je kunt het besteladvies per artikel handmatig aanpassen als je dat nodig vindt. Klik daarna op "Goedkeuren en exporteren".

**Stap 4 — Bestelling versturen (pagina: "Export")**

Per leverancier:
- Klik op "Mail naar [leverancier]" → opent je e-mailprogramma met kant-en-klare bestelling
- Of: Download CSV en verstuur handmatig

**De volgende ochtend:**

- Open de app
- Ga naar "Dag afsluiten"
- Vul bij "Werkelijk resultaat van gisteren" in hoeveel bonnen er daadwerkelijk waren
- Dit is het leersignaal — het systeem past zijn correctiefactoren hierop aan

---

## 7. Wat de manager bijhoudt

De manager is verantwoordelijk voor het aanleveren van de volgende gegevens. Zonder deze invoer werkt het systeem niet:

### Dagelijks (verplicht)

| Gegeven | Waar | Waarvoor |
|---------|------|----------|
| Bonnen vandaag | Sluitscherm | Basis voor baseline + leermodel |
| Omzet vandaag | Sluitscherm | Omzetprognose morgen |
| Sluitstock (per artikel) | Sluitscherm — data editor | Besteladvies berekening |
| Werkelijk bonnen van gisteren | Sluitscherm (sectie onderaan) | Bijsturen leermodel |

### Dagelijks (aanbevolen)

| Gegeven | Waar | Waarvoor |
|---------|------|----------|
| Reserveringen morgen | Sluitscherm | Correctie op baseline |
| Bijzonderheden | Sluitscherm | Patroonherkenning in leermodel |

### Periodiek (indien van toepassing)

| Gegeven | Waar | Wanneer |
|---------|------|---------|
| Party platter bestellingen | Sluitscherm | Alleen bij catering-orders |
| Handmatige voorraadcorrectie | Inventaris → Correctie formulier | Na levering, verspilling of hertelling |

### Eenmalig / door admin

| Gegeven | Waar | Wanneer |
|---------|------|---------|
| Nieuwe klant aanmaken | Beheer → Klanten | Bij onboarding nieuwe tenant |
| Nieuwe gebruiker aanmaken | Beheer → Gebruikers | Bij nieuw personeelslid |

---

## 8. Wat het systeem automatisch overneemt

### Automatisch berekend (geen actie nodig)

| Taak | Hoe |
|------|-----|
| Baseline per weekdag | Gemiddelde van laatste 4 gelijke weekdagen uit sales_history |
| Trendcorrectie | Verhouding laatste 14 dagen vs. vorige 14 dagen |
| Weerscorrectie | Ophalen via Open-Meteo API — automatisch verwerkt in forecast |
| Event multipliers | Automatisch geladen uit events.csv op basis van datum morgen |
| Reserveringscorrectie | Factor op basis van gereserveerde covers vs. normale bezetting |
| Besteladvies per product | vraag_per_cover × forecast × buffer − voorraad |
| Afronden op verpakking | Per product geconfigureerd (bv. friet in zakken van 10 kg) |
| Correctiefactor per weekdag | Automatisch bijgewerkt na invullen werkelijk resultaat |
| E-mail body opmaken | Automatisch gegenereerd per leverancier |
| Party platter extra hoeveelheden | Automatisch berekend op basis van SKU-configuratie |

### Automatisch opgeslagen

| Data | Tabel | Moment |
|------|-------|--------|
| Dagcijfers (covers, omzet) | sales_history | Bij klik "Bereken forecast" |
| Sluitstock | stock_count + current_inventory | Bij klik "Bereken forecast" |
| Voorraad-audit trail | inventory_adjustments | Bij elke voorraadwijziging |
| Forecast log | forecast_log | Bij klik "Bereken forecast" |
| Theoretisch verbruik per SKU | daily_usage | Bij klik "Bereken forecast" |

---

## 9. Inventarisbeheer — hoe het werkt

Het inventarissysteem bestaat uit drie lagen:

### Laag 1: Sluitstock (dagelijks tellen)

De manager telt elke avond de voorraad van kritieke artikelen en vult dit in op het sluitscherm. Dit is de **gezaghebbende telling** — het systeem vertrouwt altijd op de manager-telling boven zijn eigen berekeningen.

De telling wordt opgeslagen in:
- `current_inventory`: actuele stand (overschrijft vorige)
- `stock_count`: historisch archief van alle tellingen
- `inventory_adjustments`: audit trail met delta en reden

### Laag 2: Handmatige correctie (inventaris-pagina)

Als er buiten de dagelijkse telling om iets verandert (levering binnengekomen, verspilling, hertelling), kan de manager dit corrigeren via de Inventaris-pagina.

Per correctie wordt vastgelegd:
- Welk artikel
- Oude stand
- Nieuwe stand
- Delta
- Reden (uit dropdown): *Telling gecorrigeerd, Verspilling/afval, Levering niet ingeboekt, Personeelsmaaltijd, Portionering afwijking, Overig*
- Vrije notitie
- Door wie + tijdstip

### Laag 3: Theoretisch verbruik (automatisch)

Het systeem berekent dagelijks het theoretische verbruik op basis van:
```
theoretisch_verbruik[SKU] = vraag_per_cover[SKU] × actual_covers_vandaag
```

Dit wordt opgeslagen in `daily_usage`. Over tijd ontstaat een patroon:
- Gemiddeld dagverbruik per SKU
- Gemiddeld verbruik per bon

Dit is zichtbaar op de Inventaris-pagina onder "Verbruikspatronen" en helpt op termijn de `vraag_per_cover` parameters te verfijnen.

### Status-indicator

De inventaris-pagina toont bij elk artikel:
- **OK** — voorraad boven minimumdrempel
- **Laag** — voorraad onder `min_stock` waarde van het product

Bij artikelen met status "Laag" verschijnt een waarschuwingsbericht.

---

## 10. Het lerende systeem

Het systeem leert automatisch en wordt nauwkeuriger naarmate er meer data is.

### Hoe het werkt

**Stap 1:** Bij elk "Bereken forecast" wordt de voorspelling opgeslagen in `forecast_log` met `actual_covers = NULL`.

**Stap 2:** De volgende dag vult de manager de werkelijke bonnen in. Het systeem schrijft dit als `actual_covers` in dezelfde rij.

**Stap 3:** Bij de volgende forecast-berekening:
```python
factor = gemiddelde(actual / predicted) over laatste 8 voltooide rijen
factor = begrensd op 0.75 – 1.30
```

Dit betekent: als het systeem de afgelopen weken structureel te laag voorspelde op vrijdag, past het de vrijdag-forecast automatisch omhoog aan.

### Vereisten

- Minimaal **3 datapunten per weekdag** voordat de correctie actief wordt
- Per weekdag een aparte correctiefactor (maandag heeft andere patronen dan zaterdag)
- Maximum correctie: ×1.30 omhoog of ×0.75 omlaag

### Leerrapport

Op de pagina "Leerrapport" ziet de manager:
- Per weekdag: gemiddelde afwijking %, correctiefactor, aantal datapunten
- Notitie-analyse: welke bijzonderheden (bv. "markt") hangen samen met afwijkingen
- Volledige forecast log

---

## 11. Gebruikers en toegangsniveaus

### Rollen

| Rol | Toegang |
|-----|---------|
| **manager** | Dag afsluiten, Forecast, Bestelreview, Export, Inventaris, Leerrapport |
| **admin** | Alles van manager + Beheer-pagina (klanten en gebruikers aanmaken) |

### Authenticatie

Inloggen via gebruikersnaam + wachtwoord. De verificatie werkt als volgt:
```python
SELECT * FROM tenant_users
WHERE username = X
  AND password = Y
  AND is_active = true
```

Na succesvol inloggen wordt in `st.session_state` opgeslagen:
- `tenant_id` — UUID van de organisatie
- `tenant_naam` — weergavenaam (bv. "Family Maarssen")
- `user_naam` — gebruikersnaam
- `user_rol` — manager of admin

Elke paginafunctie heeft toegang tot deze waarden. Alle database-queries bevatten automatisch `tenant_id` als filter — data van de ene klant is nooit zichtbaar voor een andere klant.

> **Let op:** Wachtwoorden worden momenteel opgeslagen als platte tekst. Voor productie-gebruik is bcrypt-hashing aanbevolen.

---

## 12. Multi-tenant architectuur

Het systeem ondersteunt meerdere restaurantklanten (tenants) op dezelfde database.

### Isolatie

Elke tabel heeft een `tenant_id` kolom (UUID). Alle queries filteren op `tenant_id`:
```sql
SELECT * FROM sales_history WHERE tenant_id = '11111111-...'
```

Er is **geen kruiscontaminatie** mogelijk via de applicatielaag — elke sessie bevat maar één `tenant_id` in `session_state`.

### Nieuwe klant onboarden

1. Ga naar Beheer → Klanten
2. Vul naam en slug in (bv. naam: "Restaurant De Roos", slug: "de-roos")
3. Klik "Klant aanmaken" — systeem geeft UUID terug
4. Ga naar Beheer → Gebruikers
5. Maak een manager- en/of admin-gebruiker aan voor de nieuwe klant

De nieuwe klant kan direct inloggen. Er is geen SQL of technische kennis nodig.

### Bestaande tenants

| Naam | Slug | UUID |
|------|------|------|
| Family Maarssen | family-maarssen | 11111111-1111-1111-1111-111111111111 |

---

## 13. Databasetabellen

### tenants
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | Unieke identifier, automatisch gegenereerd |
| name | TEXT | Weergavenaam van de klant |
| slug | TEXT (UNIQUE) | URL-vriendelijke identifier |
| status | TEXT | 'active' of 'inactive' |
| created_at | TIMESTAMPTZ | Aanmaakdatum |

### tenant_users
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | — |
| tenant_id | UUID (FK) | Koppeling naar tenants |
| username | TEXT | Inlognaam |
| password | TEXT | Wachtwoord (platte tekst — zie noot beveiliging) |
| role | TEXT | 'manager' of 'admin' |
| full_name | TEXT | Volledige naam |
| is_active | BOOLEAN | False = account geblokkeerd |

### sales_history
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | — |
| tenant_id | UUID (FK) | — |
| date | DATE | Datum van de dag |
| weekday | TEXT | 'Mon' t/m 'Sun' |
| covers | INTEGER | Aantal bonnen/transacties |
| revenue_eur | NUMERIC | Dagomzet in euro |
| note | TEXT | Bijzonderheden van die dag |

### forecast_log
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | — |
| tenant_id | UUID (FK) | — |
| datum | DATE | Datum waarvoor voorspeld is |
| weekdag | INTEGER | 0=maandag, 6=zondag |
| predicted_covers | INTEGER | Voorspeld aantal bonnen |
| actual_covers | INTEGER | Werkelijk gerealiseerd (ingevuld achteraf) |
| event_naam | TEXT | Naam van het event, of 'geen event' |
| omzet_werkelijk | NUMERIC | Werkelijke omzet (optioneel) |
| notitie | TEXT | Bijzonderheden van die dag |

### current_inventory
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | — |
| tenant_id | UUID (FK) | — |
| sku_id | TEXT | Productnummer (bv. 'SKU-001') |
| current_stock | NUMERIC | Actuele hoeveelheid in voorraad |
| unit | TEXT | Eenheid (kg, stuk, etc.) |
| last_updated_at | TIMESTAMPTZ | Tijdstip laatste update |
| last_updated_by | TEXT | Gebruikersnaam die het heeft bijgewerkt |

**Uniek constraint:** `(tenant_id, sku_id)` — per tenant één rij per product

### inventory_adjustments
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | — |
| tenant_id | UUID (FK) | — |
| sku_id | TEXT | Productnummer |
| adjustment_type | TEXT | 'stock_count', 'manual_correction' |
| quantity_delta | NUMERIC | Verschil (positief = meer, negatief = minder) |
| previous_stock | NUMERIC | Voorraad vóór de wijziging |
| new_stock | NUMERIC | Voorraad ná de wijziging |
| reason | TEXT | Reden voor de correctie |
| note | TEXT | Vrije notitie |
| created_by | TEXT | Gebruikersnaam |
| created_at | TIMESTAMPTZ | Tijdstip |

### daily_usage
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | — |
| tenant_id | UUID (FK) | — |
| usage_date | DATE | Datum |
| sku_id | TEXT | Productnummer |
| theoretical_usage | NUMERIC | Berekend verbruik (vraag_per_cover × covers) |
| actual_covers | INTEGER | Aantal bonnen die dag |

**Uniek constraint:** `(tenant_id, usage_date, sku_id)`

### stock_count (historisch archief)
| Kolom | Type | Omschrijving |
|-------|------|-------------|
| id | UUID (PK) | — |
| tenant_id | UUID (FK) | — |
| date | DATE | Datum van de telling |
| sku_id | TEXT | Productnummer |
| on_hand_qty | NUMERIC | Getelde hoeveelheid |
| unit | TEXT | Eenheid |
| note | TEXT | Opmerking |

---

## 14. Codestructuur

```
restaurant-besteltool/
├── app.py                  # Hoofd-applicatie, UI, navigatie, paginafuncties
├── forecast.py             # Forecastengine (baseline, trend, event, correctie, weer)
├── recommendation.py       # Besteladvies engine (vraag, buffer, afronden)
├── inventory.py            # Voorraad lezen/schrijven/analyseren
├── learning.py             # Leermodel (correctiefactoren per weekdag)
├── data_loader.py          # Data lezen/schrijven Supabase, mailto genereren
├── weather.py              # Open-Meteo API wrapper
├── db.py                   # Supabase client + tenant/user helpers
│
├── demo_data/
│   ├── products.csv        # 30 SKUs met vraag_per_cover, buffer, verpakking
│   ├── events.csv          # Geplande evenementen met multipliers
│   ├── reservations.csv    # Reserveringen met covers en party platters
│   └── sales_history.csv   # Demo verkoophistorie (fallback)
│
├── .streamlit/
│   ├── secrets.toml        # Supabase URL + key (NOOIT in git)
│   └── config.toml         # Streamlit theme configuratie (light mode)
│
├── requirements.txt        # Python dependencies
├── supabase_setup.sql      # Initiële database setup
└── supabase_migration_v2.sql # Multi-tenant migratie
```

### Python dependencies (requirements.txt)

| Package | Versie | Waarvoor |
|---------|--------|---------|
| streamlit | ≥1.36 | UI framework |
| pandas | — | Data verwerking |
| supabase | ≥2.0 | Database client |
| gotrue | — | Supabase auth dependency |
| httpx | — | HTTP client (supabase) |

---

## 15. Beveiliging

### Wat is veilig

- **Secrets in Streamlit secrets.toml** — Supabase credentials staan nooit in de code, altijd in omgevingsvariabelen
- **secrets.toml staat in .gitignore** — wordt nooit naar GitHub gepusht
- **Tenant-isolatie via applicatielaag** — elke query bevat `tenant_id`, cross-tenant queries zijn technisch onmogelijk via de UI
- **Session state** — na uitloggen wordt de volledige session_state geleegd

### Aandachtspunten

- **Wachtwoorden in platte tekst** — voor productie-gebruik dienen wachtwoorden gehasht te worden via `bcrypt`. Dit is de enige kritieke beveiligingsverbetering die nog ontbreekt.
- **Geen rate limiting** — het inlogscherm heeft geen beperking op het aantal pogingen
- **Service role key** — de Supabase key heeft volledige database-toegang; verlies van deze key geeft toegang tot alle data

### Aanbeveling voor productie

1. Implementeer bcrypt wachtwoord-hashing in `db.maak_gebruiker_aan()` en `verificeer_gebruiker()`
2. Activeer Row Level Security (RLS) op Supabase voor extra zekerheid
3. Voeg een login-pogingteller toe (max 5 pogingen per minuut)

---

*Document gegenereerd op basis van broncode — april 2026*  
*Repository: github.com/Greco-arie/restaurant-besteltool*
