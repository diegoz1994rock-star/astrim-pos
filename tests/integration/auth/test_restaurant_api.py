"""Pruebas de integración de la Fase 7 de la API HTTP de negocio (ASTRIM):
`POST /api/v1/restaurant/orders/preview`, `POST /api/v1/restaurant/orders`
— la pantalla Vendedor (`RestaurantService`/`SalesService`), contra un
`TestClient` real, con productos/inventario reales creados vía el propio
servicio (nunca INSERT directo), igual que el resto de las pruebas de esta
API.

Cada prueba de `preview` compara, cuando corresponde, contra
`SalesService.preview_sale()` llamado directo con la misma lista de líneas
— para verificar que los cálculos de la API coinciden exactamente con la
lógica que ya usa el escritorio, no una reimplementación paralela (mismo
criterio que `test_sales_api.py`)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

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
from pos.modules.sales.application.dto import SaleItemInput
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


def _create_product(
    services: _Services,
    *,
    sku: str = "SKU-1",
    name: str = "Hamburguesa",
    unit_price: Decimal = Decimal("15000"),
    track_inventory: bool = False,
):
    return services.product_service.create_product(
        sku=sku,
        name=name,
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=unit_price,
        cost_price=Decimal("8000"),
        unit_of_measure="unidad",
        track_inventory=track_inventory,
    )


def _stock_product(services: _Services, product_id: int, quantity: Decimal) -> None:
    warehouse = services.inventory_service.create_warehouse(name="Principal")
    services.inventory_service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse.id,
        quantity=quantity,
        reason="Carga inicial de prueba",
        created_by_user_id=None,
    )


# -- Preview ------------------------------------------------------------------


def test_preview_requires_authentication(seeded_user: int, services: _Services) -> None:
    product = _create_product(services)
    client = _make_client(services)

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={"items": [{"product_id": product.id, "quantity": "1"}]},
    )

    assert response.status_code == 401


def test_preview_requires_restaurant_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={"items": [{"product_id": product.id, "quantity": "1"}]},
        headers=headers,
    )

    assert response.status_code == 403


def test_preview_matches_preview_sale_calculation(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("15000"))
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={"items": [{"product_id": product.id, "quantity": "2", "note": "Sin cebolla"}]},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    expected = services.sales_service.preview_sale(
        [SaleItemInput(product_id=product.id, quantity=Decimal("2"), note="Sin cebolla")]
    )
    assert Decimal(body["subtotal"]) == expected.subtotal
    assert Decimal(body["total"]) == expected.total
    assert len(body["items"]) == 1
    assert body["items"][0]["note"] == "Sin cebolla"


def test_preview_for_unknown_product_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={"items": [{"product_id": 999999, "quantity": "1"}]},
        headers=headers,
    )

    assert response.status_code == 404


def test_preview_ignores_stock_for_products_that_do_not_track_inventory(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, track_inventory=False)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={"items": [{"product_id": product.id, "quantity": "1000"}]},
        headers=headers,
    )

    assert response.status_code == 200


def test_preview_beyond_available_stock_returns_409(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={"items": [{"product_id": product.id, "quantity": "6"}]},
        headers=headers,
    )

    assert response.status_code == 409


def test_preview_sums_quantities_of_the_same_product_before_checking_stock(
    seeded_user: int, services: _Services
) -> None:
    """Mismo criterio que `RestaurantViewModel._check_stock` (suma lo que
    ya hay del mismo producto antes de comparar contra el disponible) —
    acá, dos líneas del mismo producto en la misma solicitud."""
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={
            "items": [
                {"product_id": product.id, "quantity": "3"},
                {"product_id": product.id, "quantity": "3"},
            ]
        },
        headers=headers,
    )

    assert response.status_code == 409


def test_preview_within_available_stock_succeeds(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders/preview",
        json={"items": [{"product_id": product.id, "quantity": "5"}]},
        headers=headers,
    )

    assert response.status_code == 200


# -- Confirmar pedido -----------------------------------------------------


def test_create_order_requires_authentication(seeded_user: int, services: _Services) -> None:
    product = _create_product(services)
    client = _make_client(services)

    response = client.post(
        "/api/v1/restaurant/orders",
        json={"items": [{"product_id": product.id, "quantity": "1"}]},
    )

    assert response.status_code == 401


def test_create_order_requires_restaurant_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(
        "/api/v1/restaurant/orders",
        json={"items": [{"product_id": product.id, "quantity": "1"}]},
        headers=headers,
    )

    assert response.status_code == 403


def test_create_order_succeeds_and_appears_as_pending_without_a_sale(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders",
        json={
            "items": [{"product_id": product.id, "quantity": "2", "note": "Para llevar"}],
            "customer_name": "Juan Pérez",
            "customer_document": "123456",
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["origin"] == "vendedor"
    assert body["order_type"] == "quick"
    assert body["table_session_id"] is None
    assert body["sale_id"] is None
    assert body["customer_name"] == "Juan Pérez"
    assert body["customer_document"] == "123456"
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 2
    assert body["items"][0]["notes"] == "Para llevar"
    assert body["items"][0]["product_name"] == product.name


def test_create_order_defaults_customer_name_when_blank(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders",
        json={"items": [{"product_id": product.id, "quantity": "1"}]},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["customer_name"] == "Consumidor Final"


def test_create_order_with_empty_items_returns_422(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders", json={"items": []}, headers=headers
    )

    assert response.status_code == 422


def test_create_order_with_zero_quantity_returns_422(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders",
        json={"items": [{"product_id": product.id, "quantity": "0"}]},
        headers=headers,
    )

    assert response.status_code == 422


def test_create_order_for_unknown_product_returns_404(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders",
        json={"items": [{"product_id": 999999, "quantity": "1"}]},
        headers=headers,
    )

    assert response.status_code == 404


def test_create_order_truncates_fractional_quantity_like_the_desktop(
    seeded_user: int, services: _Services
) -> None:
    """Réplica literal de `RestaurantViewModel.confirm_order`
    (`int(item.quantity)`, trunca en vez de redondear) — no se "arregla"
    acá, se documenta y se prueba tal cual."""
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/restaurant/orders",
        json={"items": [{"product_id": product.id, "quantity": "2.9"}]},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["items"][0]["quantity"] == 2


def test_create_order_appears_in_dispatch_queue(seeded_user: int, services: _Services) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)

    create_response = client.post(
        "/api/v1/restaurant/orders",
        json={"items": [{"product_id": product.id, "quantity": "1"}], "customer_name": "Ana"},
        headers=headers,
    )
    order_id = create_response.json()["id"]

    dispatch_response = client.get("/api/v1/dispatch/orders", headers=headers)

    assert dispatch_response.status_code == 200
    order_ids = [card["order_id"] for card in dispatch_response.json()]
    assert order_id in order_ids
    card = next(c for c in dispatch_response.json() if c["order_id"] == order_id)
    assert card["origin"] == "vendedor"
    assert card["is_paid"] is False
    assert card["dispatch_status"] == "pending"
