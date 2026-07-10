"""Fixtures de integración para el módulo de reportes: SQLite real con una
venta completada, para tener datos reales que reportar."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.core.events.bus import EventBus
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.reports.application.reports_service import ReportsService
from pos.modules.roles.infrastructure.models import Role
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.users.infrastructure.models import User


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None


@dataclass(frozen=True)
class ReportsFixtures:
    reports_service: ReportsService
    today: date


@pytest.fixture
def reports_env(sqlite_engine: None, tmp_path: Path) -> ReportsFixtures:
    with session_scope() as session:
        role = Role(name="Cajero", is_system_role=True)
        session.add(role)
        session.flush()
        user = User(
            username="cajero_reportes",
            password_hash="hash-no-relevante",
            full_name="Cajero Reportes",
            role_id=role.id,
            is_active=True,
        )
        session.add(user)
        session.flush()
        user_id = user.id

    event_bus = EventBus()
    inventory_service = InventoryService(event_bus)
    cash_register_service = CashRegisterService(event_bus)
    customer_service = CustomerManagementService()
    product_service = ProductManagementService(event_bus)
    sales_service = SalesService(
        event_bus, inventory_service, cash_register_service, customer_service
    )
    reports_service = ReportsService(inventory_service)

    warehouse = inventory_service.create_warehouse(name="Bodega Reportes")
    register = cash_register_service.create_register(name="Caja Reportes")
    cash_session = cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=user_id, opening_amount=Decimal("10000")
    )
    product = product_service.create_product(
        sku="REP-1",
        name="Producto Reporte",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("1000"),
        cost_price=Decimal("500"),
        unit_of_measure="unidad",
        track_inventory=True,
        tax_codes=set(),
    )
    inventory_service.register_entry(
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=Decimal("50"),
        reason="Stock inicial",
        created_by_user_id=user_id,
    )
    sales_service.complete_sale(
        items=[SaleItemInput(product_id=product.id, quantity=Decimal("4"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("4000"))],
        cash_session_id=cash_session.id,
        warehouse_id=warehouse.id,
        created_by_user_id=user_id,
    )
    cash_register_service.close_session(
        cash_session_id=cash_session.id, closed_by_user_id=user_id, counted_amount=Decimal("14000")
    )

    return ReportsFixtures(reports_service=reports_service, today=date.today())
