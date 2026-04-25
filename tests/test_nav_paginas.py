"""Tests voor de pagina-navigatie per rol (zie app.py PAGINAS_*).

STAP 4d (Optie A): super_admin moet "Instellingen" niet zien — die pagina is
strikt tenant-scoped en super_admin heeft geen eigen tenant_id. Cross-tenant
beheer doet super_admin via "Beheer" (PAGE_ADMIN).
"""
from __future__ import annotations

import app


def test_super_admin_ziet_geen_instellingen() -> None:
    assert app.PAGE_INSTELLINGEN not in app.PAGINAS_SUPER_ADMIN


def test_super_admin_ziet_wel_beheer() -> None:
    assert app.PAGE_ADMIN in app.PAGINAS_SUPER_ADMIN


def test_admin_ziet_instellingen() -> None:
    assert app.PAGE_INSTELLINGEN in app.PAGINAS_ADMIN


def test_manager_ziet_instellingen() -> None:
    assert app.PAGE_INSTELLINGEN in app.PAGINAS_MANAGER


def test_user_ziet_geen_instellingen() -> None:
    assert app.PAGE_INSTELLINGEN not in app.PAGINAS


def test_user_ziet_geen_beheer() -> None:
    assert app.PAGE_ADMIN not in app.PAGINAS


def test_alleen_super_admin_ziet_beheer() -> None:
    assert app.PAGE_ADMIN not in app.PAGINAS_ADMIN
    assert app.PAGE_ADMIN not in app.PAGINAS_MANAGER
    assert app.PAGE_ADMIN not in app.PAGINAS


def test_super_admin_ziet_dashboard() -> None:
    assert app.PAGE_DASHBOARD in app.PAGINAS_SUPER_ADMIN


def test_super_admin_ziet_alle_basispaginas() -> None:
    for pagina in app._PAGINAS_BASIS:
        assert pagina in app.PAGINAS_SUPER_ADMIN
