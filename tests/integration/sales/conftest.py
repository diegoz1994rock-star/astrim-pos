"""Fixtures de integración para el módulo de ventas: SQLite real con
esquema completo, bodega, caja abierta, producto con IVA y cliente."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
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
from pos.modules.products.infrastructure.models import Tax
from pos.modules.roles.infrastructure.models import Role
from pos.modules.sales.application.sale_service import SalesService
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
class SalesFixtures:
    warehouse_id: int
    cash_session_id: int
    product_id: int
    product_with_tax_id: int
    customer_id: int
    user_id: int
    sales_service: SalesService
    inventory_service: InventoryService
    cash_register_service: CashRegisterService
    customer_service: CustomerManagementService
    event_bus: EventBus


@pytest.fixture
def sales_env(sqlite_engine: None) -> SalesFixtures:
    with session_scope() as session:
        role = Role(name="Cajero", is_system_role=True)
        session.add(role)
        session.flush()
        user = User(
            username="cajero_ventas",
            password_hash="hash-no-relevante",
            full_name="Cajero de Ventas",
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

    warehouse = inventory_service.create_warehouse(name="Bodega Ventas")
    register = cash_register_service.create_register(name="Caja Ventas")
    cash_session = cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=user_id, opening_amount=Decimal("100000")
    )
    customer = customer_service.create_customer(
        full_name="Cliente Test", credit_limit=Decimal("50000")
    )

    product = product_service.create_product(
        sku="VENTA-1",
        name="Producto Simple",
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
        quantity=Decimal("100"),
        reason="Stock inicial de prueba",
        created_by_user_id=None,
    )

    with session_scope() as session:
        tax = Tax(name="IVA-TEST", rate_percent=Decimal("19"))
        session.add(tax)

    product_with_tax = product_service.create_product(
        sku="VENTA-2",
        name="Producto Con Impuesto",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("1000"),
        cost_price=Decimal("500"),
        unit_of_measure="unidad",
        track_inventory=True,
        tax_codes={"IVA-TEST"},
    )
    inventory_service.register_entry(
        product_id=product_with_tax.id,
        warehouse_id=warehouse.id,
        quantity=Decimal("100"),
        reason="Stock inicial de prueba",
        created_by_user_id=None,
    )

    return SalesFixtures(
        warehouse_id=warehouse.id,
        cash_session_id=cash_session.id,
        product_id=product.id,
        product_with_tax_id=product_with_tax.id,
        customer_id=customer.id,
        user_id=user_id,
        sales_service=sales_service,
        inventory_service=inventory_service,
        cash_register_service=cash_register_service,
        customer_service=customer_service,
        event_bus=event_bus,
    )
