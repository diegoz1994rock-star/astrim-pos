"""Pruebas de integración de la Fase 5 de la API HTTP de negocio (ASTRIM):
`GET /api/v1/customers`, `POST /api/v1/customers`,
`POST /api/v1/customers/{id}/payments` — contra un `TestClient` real, con
clientes reales creados vía `CustomerManagementService` (nunca INSERT
directo), igual que el resto de las pruebas de esta API."""

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
from pos.modules.customers.infrastructure.models import CreditMovementType
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


# -- Listado ------------------------------------------------------------------


def test_list_customers_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/customers")

    assert response.status_code == 401


def test_list_customers_does_not_require_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    """A diferencia de crear/abonar, listar no exige `customers.manage`:
    el escritorio lo llama sin restricción propia desde el buscador de
    cliente registrado de Ventas (`sale_view_model.py`)."""
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.get("/api/v1/customers", headers=headers)

    assert response.status_code == 200


def test_list_customers_returns_seeded_customer(seeded_user: int, services: _Services) -> None:
    services.customer_service.create_customer(
        full_name="Juan Pérez", document_id="123456", phone="3001234567",
        credit_limit=Decimal("50000"),
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/customers", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["full_name"] == "Juan Pérez"
    assert body[0]["document_id"] == "123456"
    assert Decimal(body[0]["credit_limit"]) == Decimal("50000")
    assert Decimal(body[0]["current_debt"]) == Decimal("0")
    assert body[0]["loyalty_points_balance"] == 0


def test_list_customers_empty_when_none_seeded(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/customers", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


# -- Alta -----------------------------------------------------------------


def test_create_customer_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.post("/api/v1/customers", json={"full_name": "Juan Pérez"})

    assert response.status_code == 401


def test_create_customer_requires_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(
        "/api/v1/customers", json={"full_name": "Juan Pérez"}, headers=headers
    )

    assert response.status_code == 403


def test_create_customer_success(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/customers",
        json={
            "full_name": "Juan Pérez",
            "document_id": "123456",
            "email": "juan@example.com",
            "phone": "3001234567",
            "address": "Calle 1 # 2-3",
            "credit_limit": "100000",
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Juan Pérez"
    assert body["email"] == "juan@example.com"
    assert Decimal(body["credit_limit"]) == Decimal("100000")
    assert Decimal(body["current_debt"]) == Decimal("0")
    assert len(services.customer_service.list_customers()) == 1


def test_create_customer_defaults_credit_limit_to_zero(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/customers", json={"full_name": "Juan Pérez"}, headers=headers
    )

    assert response.status_code == 201
    assert Decimal(response.json()["credit_limit"]) == Decimal("0")


def test_create_customer_with_empty_name_returns_422(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post("/api/v1/customers", json={"full_name": "   "}, headers=headers)

    assert response.status_code == 422


def test_create_customer_with_negative_credit_limit_returns_422(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/customers",
        json={"full_name": "Juan Pérez", "credit_limit": "-1"},
        headers=headers,
    )

    assert response.status_code == 422


# -- Abono ------------------------------------------------------------------


def test_register_payment_requires_manage_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    customer = services.customer_service.create_customer(full_name="Juan Pérez")
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.post(
        f"/api/v1/customers/{customer.id}/payments", json={"amount": "1000"}, headers=headers
    )

    assert response.status_code == 403


def test_register_payment_reduces_current_debt(seeded_user: int, services: _Services) -> None:
    customer = services.customer_service.create_customer(
        full_name="Juan Pérez", credit_limit=Decimal("100000")
    )
    services.customer_service.register_credit_movement(
        customer_id=customer.id, movement_type=CreditMovementType.CHARGE, amount=Decimal("30000")
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        f"/api/v1/customers/{customer.id}/payments",
        json={"amount": "20000", "reference": "efectivo"},
        headers=headers,
    )

    assert response.status_code == 200
    assert Decimal(response.json()["current_debt"]) == Decimal("10000")


def test_register_payment_on_unknown_customer_returns_404(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/customers/999999/payments", json={"amount": "1000"}, headers=headers
    )

    assert response.status_code == 404


def test_register_payment_exceeding_debt_returns_422(
    seeded_user: int, services: _Services
) -> None:
    customer = services.customer_service.create_customer(
        full_name="Juan Pérez", credit_limit=Decimal("100000")
    )
    services.customer_service.register_credit_movement(
        customer_id=customer.id, movement_type=CreditMovementType.CHARGE, amount=Decimal("10000")
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        f"/api/v1/customers/{customer.id}/payments", json={"amount": "20000"}, headers=headers
    )

    assert response.status_code == 422
