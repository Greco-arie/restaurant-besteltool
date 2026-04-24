"""Gedeelde pytest fixtures voor Restaurant Besteltool tests."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path

import pytest
from models import WeatherData, ForecastResult, UserSession, ClosingData, SupplierData, Product


# ── Supabase-secrets voor tests ─────────────────────────────────────────────
# db.py leest uit st.secrets, maar buiten Streamlit-runtime bestaat die niet.
# We monkeypatchen st.secrets met dummy-waarden (voldoende voor unit-tests) of
# met echte waarden uit .env.test (voor integration-tests tegen live Supabase).

def _laad_env_test() -> None:
    """Laad .env.test als het bestaat. Stil falen als python-dotenv ontbreekt."""
    env_test = Path(__file__).resolve().parent.parent / ".env.test"
    if not env_test.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_test, override=False)
    except ImportError:
        pass


@pytest.fixture(scope="session", autouse=True)
def _patch_streamlit_secrets():
    """
    Autouse session-fixture: zet st.secrets naar een test-dict.

    Waarden komen uit os.environ (optioneel geladen uit .env.test) of vallen
    terug op veilige dummies. Unit-tests gebruiken de dummies; integration-
    tests hebben echte secrets nodig en checken die zelf.
    """
    _laad_env_test()

    import streamlit as st
    test_secrets = {
        "supabase": {
            "url":         os.environ.get("SUPABASE_URL",         "https://dummy.supabase.co"),
            "anon_key":    os.environ.get("SUPABASE_ANON_KEY",    "dummy_anon_key"),
            "service_key": os.environ.get("SUPABASE_SERVICE_KEY", "dummy_service_key"),
            "jwt_secret":  os.environ.get("SUPABASE_JWT_SECRET",  "dummy_jwt_secret_unit_tests_only"),
        },
    }
    origineel = getattr(st, "secrets", None)
    st.secrets = test_secrets  # type: ignore[assignment]
    yield
    if origineel is not None:
        st.secrets = origineel  # type: ignore[assignment]


def pytest_collection_modifyitems(config, items):
    """
    Skip integration-tests tenzij RLS_TEST_ENABLED=1.

    Integration-tests hitten een live Supabase en mogen niet standaard draaien
    (zouden falen zonder echte secrets en zouden CI-runtijd verlengen).
    """
    if os.environ.get("RLS_TEST_ENABLED") == "1":
        return
    skip = pytest.mark.skip(
        reason="Integration tests vereisen RLS_TEST_ENABLED=1 + .env.test (zie docs/rls-policies.md)"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


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
        identity_proof="a" * 64,
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
