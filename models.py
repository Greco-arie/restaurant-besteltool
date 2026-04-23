"""Pydantic v2 domeinmodellen — type-safe boundaries voor alle Supabase responses en berekeningen."""
from __future__ import annotations
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class WeatherData(BaseModel):
    """Weerinformatie van Open-Meteo voor morgen."""
    model_config = ConfigDict(frozen=True)

    temp_max:      Optional[float] = None
    precip_prob:   Optional[int]   = None
    wmo_code:      Optional[int]   = None
    omschrijving:  str             = "Onbekend"
    terras_factor: float           = Field(default=1.0, ge=0.5, le=2.0)
    drinks_factor: float           = Field(default=1.0, ge=0.5, le=2.0)
    label:         str             = ""
    icon:          str             = "❓"
    beschikbaar:   bool            = False


class ForecastResult(BaseModel):
    """Resultaat van bereken_forecast() — alle componenten getypt."""
    model_config = ConfigDict(frozen=True)

    datum_morgen:     date
    weekdag_morgen:   int   = Field(ge=0, le=6)
    forecast_covers:  int   = Field(ge=0)
    forecast_omzet:   float = Field(ge=0)
    confidence:       Literal["hoog", "gemiddeld", "laag"]
    drivers:          list[str]
    baseline:         float
    trend_factor:     float
    res_factor:       float
    covers_mult:      float
    fries_mult:       float
    desserts_mult:    float
    event_naam:       str   = "geen event"
    event_type:       str   = ""
    platters_25:      int   = 0
    platters_50:      int   = 0
    override_actief:  bool  = False
    correctie_factor: float = 1.0
    correctie_uitleg: str   = ""
    terras_factor:    float = 1.0
    drinks_factor:    float = 1.0
    weer:             WeatherData

    def as_dict(self) -> dict:
        """Backwards-compatible conversie naar dict voor legacy callers."""
        d = self.model_dump()
        d["weer"] = self.weer.model_dump()
        return d


class UserSession(BaseModel):
    """Ingelogde gebruikerscontext vanuit Supabase RPC verificeer_login."""
    model_config = ConfigDict(frozen=True)

    tenant_id:   str
    tenant_naam: str
    username:    str
    role:        Literal["user", "manager", "admin", "super_admin"]
    full_name:   str
    permissions: dict[str, bool] = Field(default_factory=dict)


class ClosingData(BaseModel):
    """Dagafsluiting ingevoerd door de manager."""
    datum_vandaag: date
    covers:        int   = Field(ge=0)
    omzet:         float = Field(ge=0)


class SupplierData(BaseModel):
    """Leverancier uit de suppliers tabel."""
    model_config = ConfigDict(frozen=True)

    id:             str
    name:           str
    email:          str           = ""
    aanhef:         str           = ""
    lead_time_days: int           = Field(default=1, ge=0, le=14)
    levert_ma:      bool          = False
    levert_di:      bool          = False
    levert_wo:      bool          = False
    levert_do:      bool          = False
    levert_vr:      bool          = False
    levert_za:      bool          = False
    levert_zo:      bool          = False
    is_active:      bool          = True


class Product(BaseModel):
    """Product uit products.csv of de toekomstige products tabel."""
    model_config = ConfigDict(frozen=True)

    id:                str
    naam:              str
    eenheid:           str
    verpakkingseenheid: float = Field(gt=0)
    vraag_per_cover:   float = Field(ge=0)
    buffer_pct:        float = Field(ge=0, le=1)
    leverancier:       Optional[str]  = None
    actief:            bool           = True
    minimumvoorraad:   float          = Field(ge=0, default=0.0)
