"""Fixtures de integración del módulo de sincronización: una estación con
base de datos SQLite real en archivo (no en memoria, mismo motivo que
`tests/integration/backups/conftest.py`)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine
from pos.core.events.bus import EventBus
from pos.core.security.session import SessionManager
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.users.application.user_management_service import UserManagementService


@dataclass(frozen=True)
class SyncFixtures:
    event_bus: EventBus
    settings: BusinessSettingsService
    service: SyncService
    auth_service: AuthenticationService
    product_service: ProductManagementService
    category_service: CategoryManagementService
    sales_service: SalesService
    inventory_service: InventoryService
    cash_register_service: CashRegisterService
    kitchen_service: KitchenService
    customer_service: CustomerManagementService
    user_service: UserManagementService
    restaurant_service: RestaurantService
    qr_payment_service: QrPaymentService
    nequi_payment_service: NequiPaymentService
    breb_payment_service: BreBPaymentService


@pytest.fixture
def sync_env(tmp_path: Path) -> Iterator[SyncFixtures]:
    db_path = tmp_path / "pos.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)

    event_bus = EventBus()
    settings = BusinessSettingsService(event_bus)
    service = SyncService(event_bus, settings)
    auth_service = AuthenticationService(SessionManager(), event_bus)
    product_service = ProductManagementService(event_bus)
    category_service = CategoryManagementService()
    inventory_service = InventoryService(event_bus)
    cash_register_service = CashRegisterService(event_bus)
    customer_service = CustomerManagementService()
    sales_service = SalesService(
        event_bus, inventory_service, cash_register_service, customer_service
    )
    restaurant_service = RestaurantService(event_bus)
    user_service = UserManagementService(event_bus)
    kitchen_service = KitchenService(
        user_service, restaurant_service, sales_service, cash_register_service
    )
    qr_payment_service = QrPaymentService()
    nequi_payment_service = NequiPaymentService()
    breb_payment_service = BreBPaymentService()

    yield SyncFixtures(
        event_bus=event_bus,
        settings=settings,
        service=service,
        auth_service=auth_service,
        product_service=product_service,
        category_service=category_service,
        sales_service=sales_service,
        inventory_service=inventory_service,
        cash_register_service=cash_register_service,
        kitchen_service=kitchen_service,
        customer_service=customer_service,
        user_service=user_service,
        restaurant_service=restaurant_service,
        qr_payment_service=qr_payment_service,
        nequi_payment_service=nequi_payment_service,
        breb_payment_service=breb_payment_service,
    )

    session_module._engine = None
    session_module._session_factory = None
