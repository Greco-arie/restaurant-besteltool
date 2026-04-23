# FASE 8 — ANALYTICS DASHBOARD
# Vereiste: Fase 7 (FastAPI endpoints live).
# Read-only, voor eigenaar/investeerder. Geen Streamlit.
# Plak dit samen met BASE_CONTEXT.md.

Tech: HTML + Tailwind CSS CDN + Chart.js CDN — geen build-stap nodig.
Geserveerd door FastAPI als static files (api/main.py mount).

──────────────────────────────────────────────────────────────
[F8.1] dashboard/index.html
──────────────────────────────────────────────────────────────
KPI-kaarten (bovenste rij):
  Omzet vandaag | Aantal bonnen | Lage voorraad alerts
  Kleurcodering: rood = urgent (<minimumvoorraad) · groen = goed

Grafieken (Chart.js):
  1. Omzet afgelopen 7 dagen (lijndiagram) → /analytics/sales
  2. Top 10 producten op vraag (horizontaal staafdiagram) → /analytics/products
  3. Forecast vs. werkelijk per weekdag (gegroepeerd staafdiagram) → /analytics/forecast-vs-actual

Actieknoppen:
  "Besteladvies genereren" → POST /orders/generate → resultaat als tabel
  "Exporteer naar CSV" → download

UX:
  Één-oogopslag bruikbaarheid · responsive (werkt op tablet) · minimale kliks
  Auto-refresh elke 5 minuten via setInterval

Authenticatie: Bearer token (tenant slug) in localStorage.
GEEN login-formulier — URL met ?token=slug is voldoende voor intern gebruik.

──────────────────────────────────────────────────────────────
[F8.2] dashboard/static/app.js
──────────────────────────────────────────────────────────────
Functies: fetchSummary() · renderKPIs() · renderCharts() · handleOrderGenerate()
Gebruik fetch() API — geen framework nodig.
Token uit localStorage meesturen als Authorization: Bearer <token>.
