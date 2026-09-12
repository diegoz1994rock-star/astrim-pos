"""Pruebas de integración de la Fase 4 de la API HTTP de negocio (ASTRIM):
`GET /api/v1/dispatch/orders`, `POST .../{id}/advance`, `POST .../{id}/deliver`
— la pantalla Despacho (`KitchenService`), contra un `TestClient` real, con
pedidos reales creados vía `RestaurantService.create_order` (nunca INSERT
directo), igual que el resto de las pruebas de esta API."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from pos.core.database.session import session_scope
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
from pos.modules.products.domain.enums import ProductType
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import OrderType
from pos.modules.restaurant.infrastructure.models import Order, OrderItem
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.server.app import create_sync_app
from pos.modules.sync.server.connection_registry import ConnectionRegistry
from pos.modules.sync.server.event_log import SyncEventLog
from pos.modules.users.application.user_management_service import UserManagementService
from tests.integration.auth.conftest import TEST_PASSWORD, TEST_USERNAME


class _Services:
    def __init__(self) -> None:
        event_bus = EventBus()
        self.product_service = ProductManagementService(event_bus)
        self.category_service = CategoryManagementService()
        self.inventory_service = InventoryService(event_bus)
        self.cash_register_service = CashRegisterService(event_bus)
        self.customer_service = CustomerManagementService()
        self.sales_service = SalesService(
            event_bus, self.inventory_service, self.cash_register_service, self.customer_service
        )
        self.restaurant_service = RestaurantService(event_bus)
        self.user_service = UserManagementService(event_bus)
        self.kitchen_service = KitchenService(
            self.user_service,
            self.restaurant_service,
            self.sales_service,
            self.cash_register_service,
        )
        self.qr_payment_service = QrPaymentService()
        self.nequi_payment_service = NequiPaymentService()
        self.breb_payment_service = BreBPaymentService()


@pytest.fixture
def services(sqlite_engine: None) -> _Services:
    return _Services()


def _make_client(services: _Services) -> TestClient:
    event_bus = EventBus()
    settings = BusinessSettingsService(event_bus)
    sync_service = SyncService(event_bus, settings)
    auth_service = AuthenticationService(SessionManager(), event_bus)
    app = create_sync_app(
        sync_service,
        SyncEventLog(),
        ConnectionRegistry(),
        auth_service,
        services.product_service,
        services.category_service,
        services.sales_service,
        services.inventory_service,
        services.cash_register_service,
        services.kitchen_service,
        services.customer_service,
        services.user_service,
        services.restaurant_service,
        services.qr_payment_service,
        services.nequi_payment_service,
        services.breb_payment_service,
    )
    return TestClient(app)


def _login_headers(client: TestClient, *, username: str = TEST_USERNAME) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _seed_order(services: _Services, *, customer_name: str = "Juan Pérez") -> int:
    product = services.product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=False,
    )
    order = services.restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(product.id, 2, "Sin hielo")],
        customer_name=customer_name,
    )
    return order.id


# -- Listado --------------------------------------------------------------


def test_list_dispatch_orders_requires_authentication(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/dispatch/orders")

    assert response.status_code == 401


def test_list_dispatch_orders_requires_kitchen_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.get("/api/v1/dispatch/orders", headers=headers)

    assert response.status_code == 403


def test_list_dispatch_orders_returns_seeded_order_as_a_card(
    seeded_user: int, services: _Services
) -> None:
    order_id = _seed_order(services, customer_name="Juan Pérez")
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/dispatch/orders", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    card = body[0]
    assert card["order_id"] == order_id
    assert card["customer_name"] == "Juan Pérez"
    assert card["origin"] == "vendedor"
    assert card["is_paid"] is False
    assert card["caja_name"] is None
    assert card["sale_id"] is None
    assert card["dispatch_status"] == "pending"
    assert card["item_count"] == 1
    assert card["total_units"] == 2
    assert len(card["items"]) == 1
    assert card["items"][0]["product_name"] == "Coca-Cola 400ml"
    assert card["items"][0]["notes"] == "Sin hielo"


def test_list_dispatch_orders_empty_when_none_seeded(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/dispatch/orders", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_list_dispatch_orders_defaults_a_null_customer_name(
    seeded_user: int, services: _Services
) -> None:
    """Regresión encontrada validando la Fase 4: `Order.customer_name` es
    nulo en la base (`infrastructure/models.py`) y hay pedidos reales,
    anteriores a que `RestaurantService.create_order` empezara a aplicar
    `DEFAULT_CUSTOMER_NAME` a un nombre vacío, con ese campo en NULL —
    `RestaurantService.create_order` ya no permite crear uno así, por eso
    se inserta directo con el modelo ORM acá para reproducir ese estado
    heredado. Antes del fix, esto tiraba `500` (`DispatchOrderCardSchema`
    exigía `customer_name` no nulo)."""
    product = services.product_service.create_product(
        sku="SKU-1", name="Coca-Cola 400ml", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=False,
    )
    with session_scope() as session:
        order = Order(order_type=OrderType.QUICK, customer_name=None)
        order.items.append(OrderItem(product_id=product.id, quantity=1, notes=None))
        session.add(order)
        session.flush()
        order_id = order.id

    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/dispatch/orders", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == order_id
    assert body[0]["customer_name"] == "Consumidor Final"


# -- Avanzar estado ---------------------------------------------------------


def test_advance_order_moves_pending_to_preparing(
    seeded_user: int, services: _Services
) -> None:
    order_id = _seed_order(services)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(f"/api/v1/dispatch/orders/{order_id}/advance", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["dispatch_status"] == "preparing"


def test_advance_order_from_preparing_marks_delivered(
    seeded_user: int, services: _Services
) -> None:
    order_id = _seed_order(services)
    client = _make_client(services)
    headers = _login_headers(client)
    client.post(f"/api/v1/dispatch/orders/{order_id}/advance", headers=headers)

    response = client.post(f"/api/v1/dispatch/orders/{order_id}/advance", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["dispatch_status"] == "delivered"


def test_advance_order_from_delivered_archives_and_removes_from_queue(
    seeded_user: int, services: _Services
) -> None:
    order_id = _seed_order(services)
    client = _make_client(services)
    headers = _login_headers(client)
    client.post(f"/api/v1/dispatch/orders/{order_id}/advance", headers=headers)
    client.post(f"/api/v1/dispatch/orders/{order_id}/advance", headers=headers)

    response = client.post(f"/api/v1/dispatch/orders/{order_id}/advance", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_advance_unknown_order_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post("/api/v1/dispatch/orders/999999/advance", headers=headers)

    assert response.status_code == 404


def test_advance_order_requires_kitchen_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    order_id = _seed_order(services)
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(f"/api/v1/dispatch/orders/{order_id}/advance", headers=headers)

    assert response.status_code == 403


# -- Marcar entregado ---------------------------------------------------------


def test_deliver_order_marks_pending_order_as_delivered_directly(
    seeded_user: int, services: _Services
) -> None:
    order_id = _seed_order(services)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(f"/api/v1/dispatch/orders/{order_id}/deliver", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["dispatch_status"] == "delivered"
    assert body[0]["items"][0]["status"] == "delivered"


def test_deliver_unknown_order_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post("/api/v1/dispatch/orders/999999/deliver", headers=headers)

    assert response.status_code == 404


def test_deliver_order_requires_kitchen_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    order_id = _seed_order(services)
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(f"/api/v1/dispatch/orders/{order_id}/deliver", headers=headers)

    assert response.status_code == 403
