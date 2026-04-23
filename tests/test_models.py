"""Tests voor Pydantic domeinmodellen — validatie, frozen, Supabase round-trips."""
from __future__ import annotations
from datetime import date
import pytest
from pydantic import ValidationError
from models import WeatherData, ForecastResult, UserSession, ClosingData, SupplierData, Product


# ── WeatherData ────────────────────────────────────────────────────────────

class TestWeatherData:
    def test_valid_beschikbaar(self, weer_beschikbaar):
        assert weer_beschikbaar.terras_factor == 1.40
        assert weer_beschikbaar.beschikbaar is True

    def test_valid_onbeschikbaar(self, weer_onbeschikbaar):
        assert weer_onbeschikbaar.beschikbaar is False
        assert weer_onbeschikbaar.terras_factor == 1.0

    def test_frozen(self, weer_beschikbaar):
        with pytest.raises(Exception):
            weer_beschikbaar.terras_factor = 2.0

    @staticmethod
    def test_terras_factor_bounds():
        with pytest.raises(ValidationError):
            WeatherData(terras_factor=3.0)

    @staticmethod
    def test_supabase_round_trip():
        raw = {
            "temp_max": 18.0, "precip_prob": 20, "wmo_code": 2,
            "omschrijving": "Gedeeltelijk bewolkt", "terras_factor": 1.18,
            "drinks_factor": 1.30, "label": "Aangenaam", "icon": "⛅", "beschikbaar": True,
        }
        w = WeatherData.model_validate(raw)
        assert w.temp_max == 18.0
        assert w.icon == "⛅"

    @staticmethod
    def test_null_fields_allowed():
        w = WeatherData(omschrijving="Niet beschikbaar")
        assert w.temp_max is None
        assert w.precip_prob is None


# ── ForecastResult ─────────────────────────────────────────────────────────

class TestForecastResult:
    def test_valid_construct(self, forecast_result):
        assert forecast_result.forecast_covers == 180
        assert forecast_result.confidence == "gemiddeld"

    def test_frozen(self, forecast_result):
        with pytest.raises(Exception):
            forecast_result.forecast_covers = 999

    def test_negative_covers_rejected(self, weer_beschikbaar):
        with pytest.raises(ValidationError):
            ForecastResult(
                datum_morgen=date(2026, 4, 17), weekdag_morgen=3,
                forecast_covers=-1, forecast_omzet=0.0,
                confidence="laag", drivers=[], baseline=0.0,
                trend_factor=1.0, res_factor=1.0, covers_mult=1.0,
                fries_mult=1.0, desserts_mult=1.0,
                terras_factor=1.0, drinks_factor=1.0,
                weer=weer_beschikbaar,
            )

    def test_invalid_confidence(self, weer_beschikbaar):
        with pytest.raises(ValidationError):
            ForecastResult(
                datum_morgen=date(2026, 4, 17), weekdag_morgen=3,
                forecast_covers=100, forecast_omzet=1500.0,
                confidence="onbekend",
                drivers=[], baseline=100.0,
                trend_factor=1.0, res_factor=1.0, covers_mult=1.0,
                fries_mult=1.0, desserts_mult=1.0,
                terras_factor=1.0, drinks_factor=1.0,
                weer=weer_beschikbaar,
            )

    def test_as_dict_backwards_compat(self, forecast_result):
        d = forecast_result.as_dict()
        assert isinstance(d, dict)
        assert d["forecast_covers"] == 180
        assert isinstance(d["weer"], dict)
        assert d["weer"]["terras_factor"] == 1.40

    def test_weekdag_bounds(self, weer_beschikbaar):
        with pytest.raises(ValidationError):
            ForecastResult(
                datum_morgen=date(2026, 4, 17), weekdag_morgen=7,
                forecast_covers=100, forecast_omzet=0.0,
                confidence="laag", drivers=[], baseline=100.0,
                trend_factor=1.0, res_factor=1.0, covers_mult=1.0,
                fries_mult=1.0, desserts_mult=1.0,
                terras_factor=1.0, drinks_factor=1.0,
                weer=weer_beschikbaar,
            )


# ── UserSession ────────────────────────────────────────────────────────────

class TestUserSession:
    def test_valid(self, user_session):
        assert user_session.role == "manager"
        assert user_session.tenant_naam == "Family Maarssen"

    def test_frozen(self, user_session):
        with pytest.raises(Exception):
            user_session.role = "admin"

    @staticmethod
    def test_invalid_role():
        with pytest.raises(ValidationError):
            UserSession(
                tenant_id="x", tenant_naam="X", username="u",
                role="eigenaar",
                full_name="U",
            )

    @staticmethod
    def test_permissions_default_empty():
        u = UserSession(
            tenant_id="x", tenant_naam="X", username="u",
            role="user", full_name="U",
        )
        assert u.permissions == {}

    @staticmethod
    def test_supabase_round_trip():
        raw = {
            "tenant_id": "abc", "tenant_naam": "TestBedrijf",
            "username": "chef01", "role": "manager",
            "full_name": "Chef Test", "permissions": {"closing_invoeren": True},
        }
        u = UserSession.model_validate(raw)
        assert u.username == "chef01"
        assert u.permissions["closing_invoeren"] is True


# ── ClosingData ────────────────────────────────────────────────────────────

class TestClosingData:
    def test_valid(self, closing_data):
        assert closing_data.covers == 155
        assert closing_data.omzet == 2325.0

    @staticmethod
    def test_negative_covers_rejected():
        with pytest.raises(ValidationError):
            ClosingData(datum_vandaag=date(2026, 4, 16), covers=-5, omzet=0.0)

    @staticmethod
    def test_negative_omzet_rejected():
        with pytest.raises(ValidationError):
            ClosingData(datum_vandaag=date(2026, 4, 16), covers=100, omzet=-100.0)


# ── SupplierData ───────────────────────────────────────────────────────────

class TestSupplierData:
    def test_valid(self, supplier_data):
        assert supplier_data.name == "Vers & Co"
        assert supplier_data.levert_ma is True
        assert supplier_data.levert_za is False

    def test_frozen(self, supplier_data):
        with pytest.raises(Exception):
            supplier_data.name = "Andere Naam"

    @staticmethod
    def test_lead_time_max():
        with pytest.raises(ValidationError):
            SupplierData(id="x", name="X", lead_time_days=15)

    @staticmethod
    def test_lead_time_negative():
        with pytest.raises(ValidationError):
            SupplierData(id="x", name="X", lead_time_days=-1)

    @staticmethod
    def test_supabase_round_trip():
        raw = {
            "id": "sup-xyz", "name": "Slagerij Bakker",
            "email": "order@bakker.nl", "aanhef": "Beste",
            "lead_time_days": 2, "is_active": True,
            "levert_ma": True, "levert_di": False, "levert_wo": True,
            "levert_do": False, "levert_vr": True, "levert_za": False, "levert_zo": False,
            "tenant_id": "abc",
        }
        s = SupplierData.model_validate(raw)
        assert s.name == "Slagerij Bakker"
        assert s.levert_wo is True


# ── Product ────────────────────────────────────────────────────────────────

class TestProduct:
    def test_valid(self, product_data):
        assert product_data.naam == "Friet 2.5kg"
        assert product_data.buffer_pct == 0.20

    def test_frozen(self, product_data):
        with pytest.raises(Exception):
            product_data.buffer_pct = 0.50

    @staticmethod
    def test_zero_verpakkingseenheid_rejected():
        with pytest.raises(ValidationError):
            Product(id="x", naam="X", eenheid="kg",
                    verpakkingseenheid=0.0, vraag_per_cover=0.1, buffer_pct=0.2)

    @staticmethod
    def test_negative_buffer_rejected():
        with pytest.raises(ValidationError):
            Product(id="x", naam="X", eenheid="kg",
                    verpakkingseenheid=1.0, vraag_per_cover=0.1, buffer_pct=-0.1)

    @staticmethod
    def test_buffer_over_100_rejected():
        with pytest.raises(ValidationError):
            Product(id="x", naam="X", eenheid="kg",
                    verpakkingseenheid=1.0, vraag_per_cover=0.1, buffer_pct=1.5)
