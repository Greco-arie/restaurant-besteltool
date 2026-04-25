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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **restaurant-besteltool** (1709 symbols, 2653 relationships, 60 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/restaurant-besteltool/context` | Codebase overview, check index freshness |
| `gitnexus://repo/restaurant-besteltool/clusters` | All functional areas |
| `gitnexus://repo/restaurant-besteltool/processes` | All execution flows |
| `gitnexus://repo/restaurant-besteltool/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
