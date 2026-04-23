"""Gedeelde pytest fixtures voor Restaurant Besteltool tests."""
from __future__ import annotations
from datetime import date
import pytest
from models import WeatherData, ForecastResult, UserSession, ClosingData, SupplierData, Product


@pytest.fixture
def weer_beschikbaar() -> WeatherData:
    return WeatherData(
        temp_max=22.0, precip_prob=10, wmo_code=1,
        omschrijving="Overwegend helder", terras_factor=1.40,
        drinks_factor=1.60, label="Warm & droog", icon="☀️", beschikbaar=True,
    )


@pytest.fixture
def weer_onbeschikbaar() -> WeatherData:
    return WeatherData(omschrijving="Weerdata niet beschikbaar", beschikbaar=False)


@pytest.fixture
def forecast_result(weer_beschikbaar) -> ForecastResult:
    return ForecastResult(
        datum_morgen=date(2026, 4, 17),
        weekdag_morgen=3,
        forecast_covers=180,
        forecast_omzet=2700.0,
        confidence="gemiddeld",
        drivers=["Baseline: 170 bonnen", "Trend: +5%"],
        baseline=170.0,
        trend_factor=1.05,
        res_factor=1.0,
        covers_mult=1.0,
        fries_mult=1.0,
        desserts_mult=1.0,
        terras_factor=1.40,
        drinks_factor=1.60,
        weer=weer_beschikbaar,
    )


@pytest.fixture
def user_session() -> UserSession:
    return UserSession(
        tenant_id="abc-123",
        tenant_naam="Family Maarssen",
        username="manager",
        role="manager",
        full_name="Jan de Manager",
        permissions={"voorraad_tellen": True, "closing_invoeren": True},
    )


@pytest.fixture
def closing_data() -> ClosingData:
    return ClosingData(datum_vandaag=date(2026, 4, 16), covers=155, omzet=2325.0)


@pytest.fixture
def supplier_data() -> SupplierData:
    return SupplierData(
        id="sup-001", name="Vers & Co", email="bestelling@versenco.nl",
        aanhef="Geachte heer/mevrouw", lead_time_days=1,
        levert_ma=True, levert_di=True, levert_wo=True,
        levert_do=True, levert_vr=True, levert_za=False, levert_zo=False,
    )


@pytest.fixture
def product_data() -> Product:
    return Product(
        id="SKU-001", naam="Friet 2.5kg", eenheid="zak",
        verpakkingseenheid=1.0, vraag_per_cover=0.12,
        buffer_pct=0.20, leverancier="Vers & Co",
    )
