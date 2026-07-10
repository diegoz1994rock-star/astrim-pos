"""Fixtures de integración para Facturación: reutiliza el entorno completo
de Ventas (bodega, caja abierta, cliente, productos con/sin impuesto) —
para probar `BillingService` hace falta una venta real ya completada, y
`sales_env` ya construye todo lo necesario para completar una."""

from __future__ import annotations

from pathlib import Path

import pytest

from pos.modules.billing.application.billing_service import BillingService
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from tests.integration.sales.conftest import SalesFixtures, sales_env, sqlite_engine  # noqa: F401


@pytest.fixture
def billing_service(sales_env: SalesFixtures, tmp_path: Path) -> BillingService:  # noqa: F811
    settings_service = BusinessSettingsService(sales_env.event_bus)
    return BillingService(
        sales_env.sales_service,
        sales_env.customer_service,
        settings_service,
        tmp_path / "invoices",
    )
