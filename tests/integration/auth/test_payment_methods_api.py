"""Pruebas de integración de los endpoints `/api/v1/payment-methods` — el
espejo de solo lectura de la configuración de QR/Nequi/Bre-B que ya
administra el escritorio (Administración → Pagos electrónicos) y que Caja
consulta al cobrar (`get_default_config()`), contra un `TestClient` real,
con configuraciones reales creadas vía el propio servicio (nunca INSERT
directo), igual que el resto de las pruebas de esta API.

Ningún dato inventado: si el escritorio no tiene un método configurado, el
endpoint responde 409 (ver `payment_methods_router.py`) — nunca un objeto
vacío."""

from __future__ import annotations

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


# -- QR -------------------------------------------------------------------


def test_get_qr_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/payment-methods/qr")

    assert response.status_code == 401


def test_get_qr_without_configuration_returns_409(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/qr", headers=headers)

    assert response.status_code == 409


def test_get_qr_returns_the_default_configuration(
    seeded_user: int, services: _Services, tmp_path
) -> None:
    image_path = tmp_path / "qr.png"
    image_path.write_bytes(b"fake-png-bytes")
    services.qr_payment_service.create_config(name="QR Bancolombia", image_path=str(image_path))
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/qr", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "QR Bancolombia"
    assert body["has_image"] is True


def test_get_qr_without_image_reports_has_image_false(
    seeded_user: int, services: _Services
) -> None:
    services.qr_payment_service.create_config(name="QR sin imagen", image_path=None)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/qr", headers=headers)

    assert response.status_code == 200
    assert response.json()["has_image"] is False


def test_get_qr_image_returns_the_configured_file(
    seeded_user: int, services: _Services, tmp_path
) -> None:
    image_path = tmp_path / "qr.png"
    image_path.write_bytes(b"fake-png-bytes")
    config = services.qr_payment_service.create_config(
        name="QR Bancolombia", image_path=str(image_path)
    )
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/payment-methods/qr/{config.id}/image", headers=headers)

    assert response.status_code == 200
    assert response.content == b"fake-png-bytes"


def test_get_qr_image_for_unknown_id_returns_404(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/qr/999/image", headers=headers)

    assert response.status_code == 404


def test_get_qr_image_without_a_stored_file_returns_404(
    seeded_user: int, services: _Services
) -> None:
    config = services.qr_payment_service.create_config(name="QR sin imagen", image_path=None)
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/payment-methods/qr/{config.id}/image", headers=headers)

    assert response.status_code == 404


# -- Nequi ------------------------------------------------------------------


def test_get_nequi_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/payment-methods/nequi")

    assert response.status_code == 401


def test_get_nequi_without_configuration_returns_409(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/nequi", headers=headers)

    assert response.status_code == 409


def test_get_nequi_returns_the_default_configuration(
    seeded_user: int, services: _Services
) -> None:
    services.nequi_payment_service.create_config(number="3001234567")
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/nequi", headers=headers)

    assert response.status_code == 200
    assert response.json()["number"] == "3001234567"


# -- Bre-B --------------------------------------------------------------------


def test_get_breb_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/payment-methods/bre-b")

    assert response.status_code == 401


def test_get_breb_without_configuration_returns_409(
    seeded_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/bre-b", headers=headers)

    assert response.status_code == 409


def test_get_breb_returns_the_default_configuration(
    seeded_user: int, services: _Services
) -> None:
    services.breb_payment_service.create_config(key="user@banco.breb")
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/payment-methods/bre-b", headers=headers)

    assert response.status_code == 200
    assert response.json()["key"] == "user@banco.breb"
