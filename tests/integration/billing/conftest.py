"""Fixtures de integración para Facturación: reutiliza el entorno completo
de Ventas (bodega, caja abierta, cliente, productos con/sin impuesto) —
para probar `BillingService` hace falta una venta real ya completada, y
`sales_env` ya construye todo lo necesario para completar una."""

from __future__ import annotations

from pathlib import Path

import pytest

from pos.modules.billing.application.billing_service import BillingService
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.users.application.user_management_service import UserManagementService
from tests.integration.sales.conftest import SalesFixtures, sales_env, sqlite_engine  # noqa: F401


@pytest.fixture
def cash_drawer_service(sales_env: SalesFixtures) -> CashDrawerService:  # noqa: F811
    return CashDrawerService(sales_env.event_bus, sales_env.cash_register_service)


@pytest.fixture
def printer_service(sales_env: SalesFixtures) -> PrinterService:  # noqa: F811
    return PrinterService(sales_env.event_bus)


@pytest.fixture
def billing_service(
    sales_env: SalesFixtures,  # noqa: F811
    cash_drawer_service: CashDrawerService,
    tmp_path: Path,
) -> BillingService:
    settings_service = BusinessSettingsService(sales_env.event_bus)
    invoice_settings_service = InvoiceSettingsService()
    user_service = UserManagementService(sales_env.event_bus)
    return BillingService(
        sales_env.sales_service,
        sales_env.customer_service,
        settings_service,
        invoice_settings_service,
        user_service,
        sales_env.cash_register_service,
        cash_drawer_service,
        tmp_path / "invoices",
    )
