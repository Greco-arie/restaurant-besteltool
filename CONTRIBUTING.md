# Branch strategie

## Branches

| Branch | Doel | Auto-deploy |
|--------|------|-------------|
| `main` | Productie | Streamlit Cloud (live) |
| `staging` | Staging omgeving | Streamlit Cloud (staging) |
| `feature/*` | Feature development | — |

## Werkwijze

1. Maak een feature branch aan: `git checkout -b feature/naam-van-feature`
2. Ontwikkel en test lokaal
3. Merge naar `staging` en test op de staging omgeving
4. Pas je merge toe naar `main` zodra staging groen is

## Regels

- **Nooit direct naar `main` pushen** zonder eerst op staging te testen
- Elke push triggert automatisch de CI (GitHub Actions: tests draaien)
- PR's naar `main` vereisen een goedkeuring van de beheerder

## Lokaal testen

```bash
pip install -r requirements.txt
pytest tests/ -v
```
