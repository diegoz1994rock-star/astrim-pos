"""Pruebas de integración de la Fase 1 de la API HTTP de negocio (ASTRIM):
`POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET /api/v1/health` y el
middleware de autenticación — contra un `TestClient` real de FastAPI (no
mocks de la app), con SQLite real de fondo.

No arranca Uvicorn/un puerto real (eso ya lo cubre
`tests/integration/sync/test_sync_server_lifecycle.py`) — `TestClient`
ejecuta la misma app ASGI en proceso, más rápido y suficiente para probar
rutas/middleware."""

from __future__ import annotations

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


def _make_client(*, session_manager: SessionManager | None = None) -> TestClient:
    event_bus = EventBus()
    settings = BusinessSettingsService(event_bus)
    sync_service = SyncService(event_bus, settings)
    auth_service = AuthenticationService(session_manager or SessionManager(), event_bus)
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
    app = create_sync_app(
        sync_service,
        SyncEventLog(),
        ConnectionRegistry(),
        auth_service,
        product_service,
        category_service,
        sales_service,
        inventory_service,
        cash_register_service,
        kitchen_service,
        customer_service,
        user_service,
        restaurant_service,
        qr_payment_service,
        nequi_payment_service,
        breb_payment_service,
    )
    return TestClient(app)


def test_health_endpoint_is_public_and_ok(sqlite_engine: None) -> None:
    client = _make_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "server_time" in body  # Fase 5: para que el cliente detecte desfase de reloj


def test_legacy_health_endpoint_still_works(sqlite_engine: None) -> None:
    """El `/health` a nivel raíz (usado por `SyncServer.probe`, ver
    `server/runner.py`) no debe verse afectado por agregar `/api/v1`."""
    client = _make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_with_valid_credentials_returns_token_and_session(seeded_user: int) -> None:
    client = _make_client()

    response = client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["token"], str) and len(body["token"]) > 20
    assert body["session"]["username"] == TEST_USERNAME
    assert body["session"]["user_id"] == seeded_user
    assert body["session"]["is_admin"] is True
    assert body["session"]["job_position_name"] == "Administrador General"


def test_login_with_invalid_credentials_returns_401(seeded_user: int) -> None:
    client = _make_client()

    response = client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": "clave-incorrecta"}
    )

    assert response.status_code == 401


def test_login_with_unknown_username_returns_401(sqlite_engine: None) -> None:
    client = _make_client()

    response = client.post(
        "/api/v1/auth/login", json={"username": "no-existe", "password": "cualquiera"}
    )

    assert response.status_code == 401


def test_login_does_not_affect_the_desktop_session_manager(seeded_user: int) -> None:
    """Mismo caso crítico que `test_authenticate_does_not_touch_the_desktop_session_manager`,
    pero de punta a punta a través de la API HTTP real — un login remoto no
    debe dejar `SessionManager.current` distinto de lo que ya tenía."""
    session_manager = SessionManager()
    client = _make_client(session_manager=session_manager)

    response = client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    assert not session_manager.is_authenticated()


def test_me_without_token_returns_401(sqlite_engine: None) -> None:
    client = _make_client()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(sqlite_engine: None) -> None:
    client = _make_client()

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer token-invalido"}
    )

    assert response.status_code == 401


def test_me_with_malformed_authorization_header_returns_401(sqlite_engine: None) -> None:
    client = _make_client()

    response = client.get("/api/v1/auth/me", headers={"Authorization": "token-sin-bearer"})

    assert response.status_code == 401


def test_me_with_valid_token_returns_the_authenticated_identity(seeded_user: int) -> None:
    client = _make_client()
    login_response = client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    token = login_response.json()["token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == TEST_USERNAME
    assert body["user_id"] == seeded_user
    assert body["is_admin"] is True
    assert body["job_position_name"] == "Administrador General"


def test_me_reflects_permission_codes_of_a_non_admin_user(
    seeded_user_with_permissions: int,
) -> None:
    client = _make_client()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "cajero_con_permiso", "password": TEST_PASSWORD},
    )
    token = login_response.json()["token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["is_admin"] is False
    assert body["permission_codes"] == ["sales.create"]
    assert body["job_position_name"] == "Cajero"


def test_me_reports_null_job_position_name_for_a_user_without_a_cargo(
    seeded_non_admin_user: int,
) -> None:
    """Mismo caso que el escritorio (`build_welcome_widget`, "Empleado"
    como respaldo): un usuario sin cargo asignado no rompe la respuesta,
    solo llega `null` — la etiqueta de respaldo es una decisión de cada
    cliente (ver `role_label` en `main.py`), no de esta API."""
    client = _make_client()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "mesero_no_admin", "password": TEST_PASSWORD},
    )
    token = login_response.json()["token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["job_position_name"] is None


# -- Fase 5: infraestructura de la API (documentación, manejo de errores) ----


def test_openapi_schema_is_reachable_without_auth(sqlite_engine: None) -> None:
    """La documentación interactiva no debe requerir token — sirve como
    punto de partida para el desarrollo del cliente Android, ver API.md."""
    client = _make_client()

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/sales/drafts" in schema["paths"]


def test_swagger_docs_page_is_reachable_without_auth(sqlite_engine: None) -> None:
    client = _make_client()

    response = client.get("/docs")

    assert response.status_code == 200


def test_uncaught_domain_error_from_a_service_still_returns_a_clean_http_error(
    seeded_user: int,
) -> None:
    """Prueba de punta a punta del manejador global de `errors.py`:
    `GET /sales/{id}` para un id inexistente deja que
    `SalesService.get_sale` lance `NotFoundError` sin ningún
    `try/except` en el router (ver Fase 5, simplificación de
    `sales_router.py`) — el manejador global debe traducirlo a 404 igual,
    nunca un 500 genérico."""
    client = _make_client()
    headers_response = client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    token = headers_response.json()["token"]

    response = client.get(
        "/api/v1/sales/999999", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
