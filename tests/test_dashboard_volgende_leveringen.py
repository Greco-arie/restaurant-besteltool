"""Tests voor _filter_en_sorteer_leveringen in views.page_dashboard.

Pure DataFrame-transformatie: filter op toekomstige leverdatum, sorteer
oplopend, beperk tot top N. Robuust tegen lege input en NULL-datums.
"""
from __future__ import annotations
from datetime import date, timedelta

import pandas as pd

from views.page_dashboard import _filter_en_sorteer_leveringen


VANDAAG = date(2026, 4, 26)


def _email(supplier: str, bestel_datum: str | None, ts: str = "2026-04-25T10:00:00") -> dict:
    return {
        "supplier_naam": supplier,
        "bestel_datum": bestel_datum,
        "status": "verzonden",
        "timestamp": ts,
    }


def test_lege_input_geeft_lege_dataframe() -> None:
    df = _filter_en_sorteer_leveringen([], VANDAAG)
    assert df.empty


def test_alleen_verleden_geeft_lege_dataframe() -> None:
    emails = [
        _email("Hanos", "2026-04-20"),
        _email("Bakkersland", "2026-04-25"),
    ]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG)
    assert df.empty


def test_filtert_verleden_eruit_en_houdt_toekomstig() -> None:
    emails = [
        _email("Hanos", "2026-04-20"),       # verleden
        _email("Bakkersland", "2026-04-28"), # toekomst
        _email("Heineken", "2026-04-26"),    # vandaag (inclusief)
    ]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG)
    assert len(df) == 2
    assert set(df["Leverancier"]) == {"Bakkersland", "Heineken"}


def test_sorteert_oplopend_dichtstbij_eerst() -> None:
    emails = [
        _email("Bakkersland", "2026-04-30"),
        _email("Hanos",       "2026-04-27"),
        _email("Heineken",    "2026-04-29"),
    ]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG)
    assert list(df["Leverancier"]) == ["Hanos", "Heineken", "Bakkersland"]


def test_null_bestel_datum_wordt_uitgefilterd() -> None:
    emails = [
        _email("Hanos", None),
        _email("Bakkersland", "2026-04-28"),
    ]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG)
    assert len(df) == 1
    assert df["Leverancier"].iloc[0] == "Bakkersland"


def test_kolomnamen_zijn_hernoemd() -> None:
    emails = [_email("Hanos", "2026-04-28")]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG)
    assert list(df.columns) == ["Leverancier", "Leverdatum", "Status", "Verzonden"]


def test_beperkt_tot_max_aantal() -> None:
    start = date(2026, 4, 27)
    emails = [
        _email(f"Lev-{i}", (start + timedelta(days=i)).isoformat())
        for i in range(10)
    ]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG, max_rijen=5)
    assert len(df) == 5
    # Eerste 5 oplopend
    assert list(df["Leverancier"]) == [f"Lev-{i}" for i in range(5)]


def test_verzonden_kolom_is_geformatteerd() -> None:
    emails = [_email("Hanos", "2026-04-28", ts="2026-04-25T14:30:00")]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG)
    # Format "%d/%m %H:%M" verwacht
    assert df["Verzonden"].iloc[0] == "25/04 14:30"


def test_malformed_timestamp_geeft_lege_string() -> None:
    emails = [_email("Hanos", "2026-04-28", ts="not-a-timestamp")]
    df = _filter_en_sorteer_leveringen(emails, VANDAAG)
    assert df["Verzonden"].iloc[0] == ""
