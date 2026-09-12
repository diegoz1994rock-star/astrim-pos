"""Pruebas de integración de la Fase 6 de la API HTTP de negocio (ASTRIM):
`GET /api/v1/cash-register/status`, `POST .../sessions/open`,
`POST .../sessions/close` — la pantalla Caja (`CashRegisterService`),
contra un `TestClient` real, con puntos de caja/turnos reales creados vía
el propio servicio (nunca INSERT directo), igual que el resto de las
pruebas de esta API."""

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
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
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


# -- Estado -------------------------------------------------------------------


def test_get_status_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/cash-register/status")

    assert response.status_code == 401


def test_get_status_requires_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.get("/api/v1/cash-register/status", headers=headers)

    assert response.status_code == 403


def test_get_status_without_registers_returns_409(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/cash-register/status", headers=headers)

    assert response.status_code == 409


def test_get_status_with_no_open_session_returns_null_session(
    seeded_user: int, services: _Services
) -> None:
    services.cash_register_service.create_register(name="Caja Principal")
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/cash-register/status", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["cash_register"]["name"] == "Caja Principal"
    assert body["session"] is None


def test_get_status_with_open_session_returns_it(seeded_user: int, services: _Services) -> None:
    register = services.cash_register_service.create_register(name="Caja Principal")
    services.cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=seeded_user, opening_amount=Decimal("50000")
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/cash-register/status", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["status"] == "open"
    assert Decimal(body["session"]["opening_amount"]) == Decimal("50000")
    assert body["session"]["closed_at"] is None


# -- Apertura -------------------------------------------------------------


def test_open_session_requires_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    services.cash_register_service.create_register(name="Caja Principal")
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(
        "/api/v1/cash-register/sessions/open",
        json={"opening_amount": "50000"},
        headers=headers,
    )

    assert response.status_code == 403


def test_open_session_success(seeded_user: int, services: _Services) -> None:
    services.cash_register_service.create_register(name="Caja Principal")
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/cash-register/sessions/open",
        json={"opening_amount": "50000"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert Decimal(body["opening_amount"]) == Decimal("50000")
    assert body["opened_by_user_id"] == seeded_user


def test_open_session_with_negative_amount_returns_422(
    seeded_user: int, services: _Services
) -> None:
    services.cash_register_service.create_register(name="Caja Principal")
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/cash-register/sessions/open",
        json={"opening_amount": "-1"},
        headers=headers,
    )

    assert response.status_code == 422


def test_open_session_when_already_open_returns_422(
    seeded_user: int, services: _Services
) -> None:
    register = services.cash_register_service.create_register(name="Caja Principal")
    services.cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=seeded_user, opening_amount=Decimal("50000")
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/cash-register/sessions/open",
        json={"opening_amount": "10000"},
        headers=headers,
    )

    assert response.status_code == 422


def test_open_session_without_registers_returns_409(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/cash-register/sessions/open",
        json={"opening_amount": "50000"},
        headers=headers,
    )

    assert response.status_code == 409


# -- Cierre -----------------------------------------------------------------


def test_close_session_requires_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    register = services.cash_register_service.create_register(name="Caja Principal")
    services.cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=1, opening_amount=Decimal("50000")
    )
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(
        "/api/v1/cash-register/sessions/close",
        json={"counted_amount": "50000"},
        headers=headers,
    )

    assert response.status_code == 403


def test_close_session_without_open_session_returns_409(
    seeded_user: int, services: _Services
) -> None:
    services.cash_register_service.create_register(name="Caja Principal")
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/cash-register/sessions/close",
        json={"counted_amount": "0"},
        headers=headers,
    )

    assert response.status_code == 409


def test_close_session_reports_difference(seeded_user: int, services: _Services) -> None:
    register = services.cash_register_service.create_register(name="Caja Principal")
    services.cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=seeded_user, opening_amount=Decimal("50000")
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/cash-register/sessions/close",
        json={"counted_amount": "49000"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert Decimal(body["closing_amount"]) == Decimal("49000")
    assert Decimal(body["expected_amount"]) == Decimal("50000")
    assert Decimal(body["difference"]) == Decimal("-1000")
    assert body["closed_at"] is not None


def test_close_session_with_negative_amount_returns_422(
    seeded_user: int, services: _Services
) -> None:
    register = services.cash_register_service.create_register(name="Caja Principal")
    services.cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=seeded_user, opening_amount=Decimal("50000")
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/cash-register/sessions/close",
        json={"counted_amount": "-1"},
        headers=headers,
    )

    assert response.status_code == 422


def test_get_status_after_close_shows_no_open_session_again(
    seeded_user: int, services: _Services
) -> None:
    register = services.cash_register_service.create_register(name="Caja Principal")
    services.cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=seeded_user, opening_amount=Decimal("50000")
    )
    client = _make_client(services)
    headers = _login_headers(client)
    client.post(
        "/api/v1/cash-register/sessions/close", json={"counted_amount": "50000"}, headers=headers
    )

    response = client.get("/api/v1/cash-register/status", headers=headers)

    assert response.status_code == 200
    assert response.json()["session"] is None
