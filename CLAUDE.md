# Restaurant Forecast & Besteladvies V1

## Wat dit is
Een operationele tool voor restaurant-managers: van closing naar onderbouwd besteladvies in een paar minuten.

## Stack
- Python 3.13
- Streamlit (multi-page UI)
- Pandas (forecast- en bestellogica)
- SQLite (dataopslag via sqlite3, ingebouwd in Python)
- CSV (demo-data + import/export)

## Mapstructuur
```
restaurant besteltool/
├── CLAUDE.md           ← dit bestand
├── requirements.txt    ← Python dependencies
├── setup.sh            ← eenmalige setup
├── app.py              ← Streamlit entry point
├── forecast.py         ← forecastengine
├── recommendation.py   ← bestelengine
├── data_loader.py      ← CSV/SQLite laadlogica
├── demo_data/          ← CSV-bestanden voor demo
│   ├── products.csv
│   ├── sales_history.csv
│   ├── reservations.csv
│   ├── stock_count.csv
│   └── events.csv
├── data/               ← SQLite database (gitignore)
└── docs/               ← Masterdocument en notities
```

## Projectregels
1. AI berekent NIETS — alleen uitleg en tekst genereren
2. Forecastformule: baseline × trend × reservering × event (+ manager override)
3. Bestelformule: verwachte_vraag + buffer - voorraad - openstaand (min 0, ceil op verpakking)
4. Altijd uitlegbaar: elke afwijking heeft een reden
5. Manager kan altijd handmatig corrigeren
6. Geen API's, geen accounts, geen automatisch verzenden in V1

## Starten
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Demo-scenario's (Blok 7)
- Scenario 1: Normale woensdag → standaard besteladvies
- Scenario 2: Moederdag zaterdag → hogere forecast, duidelijke afwijking

## Relevante FOR CLAUDE bestanden
- `skills/python/streamlit.md` — Streamlit patronen
- `skills/python/pandas-forecast.md` — Forecastberekeningen
- `skills/python/sqlite-local.md` — SQLite patronen
- `agents/custom/horeca-logica.md` — Domeinlogica reviewer
- `workflows/restaurant-forecast-build.md` — Bouwvolgorde (7 blokken)
