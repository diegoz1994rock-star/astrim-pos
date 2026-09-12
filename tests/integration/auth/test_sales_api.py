"""Pruebas de integración de la Fase 3 de la API HTTP de negocio (ASTRIM):
`POST /api/v1/sales/drafts`, `GET .../{id}`, `POST .../{id}/items`,
`PATCH .../{id}/items/{index}`, `DELETE .../{id}/items/{index}` — el
proceso universal de construcción de una venta, sin cobro (eso es Fase 4).

Cada prueba compara, cuando corresponde, contra
`SalesService.preview_sale()` llamado directo con la misma lista de líneas
— para verificar que los cálculos de la API coinciden exactamente con la
lógica que ya usa el escritorio, no una reimplementación paralela."""

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
        self.product_service = ProductManagementService(EventBus())
        self.category_service = CategoryManagementService()
        self.inventory_service = InventoryService(EventBus())
        self.cash_register_service = CashRegisterService(EventBus())
        self.customer_service = CustomerManagementService()
        self.sales_service = SalesService(
            EventBus(), self.inventory_service, self.cash_register_service, self.customer_service
        )
        self.restaurant_service = RestaurantService(EventBus())
        self.user_service = UserManagementService(EventBus())
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
    name: str = "Coca-Cola 400ml",
    unit_price: Decimal = Decimal("3500"),
    track_inventory: bool = False,
):
    return services.product_service.create_product(
        sku=sku,
        name=name,
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=unit_price,
        cost_price=Decimal("2000"),
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


def _open_cash_session(
    services: _Services, *, opened_by_user_id: int, opening_amount: Decimal = Decimal("0")
) -> None:
    """Mismo requisito que exige el escritorio antes de cobrar: un punto
    de caja con un turno abierto (`CashRegisterService.get_open_session`,
    ver `SaleViewModel.complete_sale`)."""
    register = services.cash_register_service.create_register(name="Caja 1")
    services.cash_register_service.open_session(
        cash_register_id=register.id,
        opened_by_user_id=opened_by_user_id,
        opening_amount=opening_amount,
    )


def _ready_for_checkout(services: _Services, *, opened_by_user_id: int) -> None:
    """Deja listo lo mínimo que `complete_sale` exige siempre — igual que
    `SaleViewModel.complete_sale` del escritorio: al menos una bodega (para
    cualquier venta, tenga o no líneas con inventario) y un turno de caja
    abierto."""
    services.inventory_service.create_warehouse(name="Principal")
    _open_cash_session(services, opened_by_user_id=opened_by_user_id)


# -- Crear / consultar el carrito ---------------------------------------------


def test_create_draft_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.post("/api/v1/sales/drafts")

    assert response.status_code == 401


def test_create_draft_returns_an_empty_sale(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post("/api/v1/sales/drafts", headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["items"] == []
    assert body["subtotal"] == "0"
    assert body["total"] == "0"
    assert body["draft_id"]


def test_get_unknown_draft_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/sales/drafts/no-existe", headers=headers)

    assert response.status_code == 404


def test_get_draft_from_another_user_returns_404(
    seeded_user: int, seeded_user_with_permissions: int, services: _Services
) -> None:
    """Un carrito solo lo puede ver/editar quien lo creó — mismo criterio
    de autorización de la Fase 1 (token → identidad)."""
    client = _make_client(services)
    owner_headers = _login_headers(client, username=TEST_USERNAME)
    draft_id = client.post("/api/v1/sales/drafts", headers=owner_headers).json()["draft_id"]

    other_headers = _login_headers(client, username="cajero_con_permiso")
    response = client.get(f"/api/v1/sales/drafts/{draft_id}", headers=other_headers)

    assert response.status_code == 404


# -- Agregar productos ---------------------------------------------------------


def test_add_item_matches_preview_sale_calculation(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("3500"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "2"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    expected = services.sales_service.preview_sale(
        [SaleItemInput(product_id=product.id, quantity=Decimal("2"))]
    )
    assert Decimal(body["subtotal"]) == expected.subtotal
    assert Decimal(body["tax_total"]) == expected.tax_total
    assert Decimal(body["total"]) == expected.total
    assert Decimal(body["total"]) == Decimal("7000")
    assert len(body["items"]) == 1
    assert body["items"][0]["product_name"] == "Coca-Cola 400ml"


def test_add_same_product_twice_merges_into_one_line(
    seeded_user: int, services: _Services
) -> None:
    """Mismo comportamiento que `SaleViewModel.add_item` del escritorio:
    agregar un producto ya presente suma la cantidad a esa línea en vez de
    crear una línea duplicada."""
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )
    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "2"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == "3"


def test_add_item_keeps_existing_note_when_not_provided(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1", "note": "Sin hielo"},
        headers=headers,
    )
    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    assert response.json()["items"][0]["note"] == "Sin hielo"


def test_add_item_for_unknown_product_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": 999999, "quantity": "1"},
        headers=headers,
    )

    assert response.status_code == 404


def test_add_item_with_zero_quantity_returns_422(seeded_user: int, services: _Services) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "0"},
        headers=headers,
    )

    assert response.status_code == 422


def test_add_item_beyond_available_stock_returns_409(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "10"},
        headers=headers,
    )

    assert response.status_code == 409


def test_add_item_within_available_stock_succeeds(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "5"},
        headers=headers,
    )

    assert response.status_code == 200


# -- Modificar cantidades -------------------------------------------------------


def test_update_item_quantity(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/sales/drafts/{draft_id}/items/0",
        json={"quantity": "4"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["quantity"] == "4"
    assert Decimal(body["total"]) == Decimal("4000")


def test_update_item_replaces_note_even_when_omitted(
    seeded_user: int, services: _Services
) -> None:
    """A diferencia de `add_item`, `update_item` del escritorio siempre
    reemplaza la nota (incluso a `None`), nunca conserva la anterior — se
    replica la misma asimetría."""
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1", "note": "Sin hielo"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/sales/drafts/{draft_id}/items/0",
        json={"quantity": "1"},
        headers=headers,
    )

    assert response.json()["items"][0]["note"] is None


def test_update_item_out_of_range_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.patch(
        f"/api/v1/sales/drafts/{draft_id}/items/0",
        json={"quantity": "1"},
        headers=headers,
    )

    assert response.status_code == 404


def test_update_item_with_zero_quantity_returns_422(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/sales/drafts/{draft_id}/items/0",
        json={"quantity": "0"},
        headers=headers,
    )

    assert response.status_code == 422


def test_update_item_beyond_available_stock_returns_409(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "5"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/sales/drafts/{draft_id}/items/0",
        json={"quantity": "6"},
        headers=headers,
    )

    assert response.status_code == 409


def test_update_item_to_same_quantity_does_not_double_count_stock(
    seeded_user: int, services: _Services
) -> None:
    """La línea que se está editando se excluye de "ya está en el
    carrito" al validar stock — igual que `_check_stock(..., exclude_index=...)`
    del escritorio; si no se excluyera, hasta mantener la misma cantidad
    fallaría por contarla dos veces."""
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "5"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/sales/drafts/{draft_id}/items/0",
        json={"quantity": "5"},
        headers=headers,
    )

    assert response.status_code == 200


# -- Eliminar productos ----------------------------------------------------------


def test_remove_item(seeded_user: int, services: _Services) -> None:
    product = _create_product(services)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.delete(f"/api/v1/sales/drafts/{draft_id}/items/0", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == "0"


def test_remove_item_out_of_range_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.delete(f"/api/v1/sales/drafts/{draft_id}/items/0", headers=headers)

    assert response.status_code == 404


# -- Flujo completo, resumen actualizado en cada paso -----------------------------


def test_full_cart_flow_keeps_summary_accurate_at_every_step(
    seeded_user: int, services: _Services
) -> None:
    soda = _create_product(services, sku="SODA", name="Gaseosa", unit_price=Decimal("3000"))
    chips = _create_product(services, sku="CHIPS", name="Papas", unit_price=Decimal("2000"))
    client = _make_client(services)
    headers = _login_headers(client)

    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": soda.id, "quantity": "2"},
        headers=headers,
    )
    body = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": chips.id, "quantity": "1"},
        headers=headers,
    ).json()
    assert Decimal(body["total"]) == Decimal("8000")  # 2*3000 + 1*2000

    body = client.patch(
        f"/api/v1/sales/drafts/{draft_id}/items/0",
        json={"quantity": "1"},
        headers=headers,
    ).json()
    assert Decimal(body["total"]) == Decimal("5000")  # 1*3000 + 1*2000

    body = client.get(f"/api/v1/sales/drafts/{draft_id}", headers=headers).json()
    assert Decimal(body["total"]) == Decimal("5000")

    body = client.delete(f"/api/v1/sales/drafts/{draft_id}/items/1", headers=headers).json()
    assert Decimal(body["total"]) == Decimal("3000")
    assert len(body["items"]) == 1
    assert body["items"][0]["product_name"] == "Gaseosa"


# -- Fase 4: finalización (cobro) ---------------------------------------------


def test_complete_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.post(
        "/api/v1/sales/drafts/no-existe/complete",
        json={"payments": [{"payment_method": "cash", "amount": "0"}]},
    )

    assert response.status_code == 401


def test_complete_requires_sales_create_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    """Un usuario sin cargo (sin `sales.create`) puede construir el
    carrito (Fase 3, sin permiso específico) pero no finalizarlo — ver
    `require_permission("sales.create")` en `sales_router.py`."""
    product = _create_product(services, unit_price=Decimal("1000"))
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "1000"}]},
        headers=headers,
    )

    assert response.status_code == 403


def test_complete_unknown_draft_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.post(
        "/api/v1/sales/drafts/no-existe/complete",
        json={"payments": [{"payment_method": "cash", "amount": "0"}]},
        headers=headers,
    )

    assert response.status_code == 404


def test_complete_empty_cart_returns_422(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "0"}]},
        headers=headers,
    )

    assert response.status_code == 422


def test_complete_without_payments_returns_422(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete", json={"payments": []}, headers=headers
    )

    assert response.status_code == 422


def test_complete_with_non_selectable_payment_method_returns_422(
    seeded_user: int, services: _Services
) -> None:
    """`transfer`/`daviplata`/`other` se conservan en el enum solo por
    compatibilidad histórica — el escritorio tampoco deja elegirlos hoy."""
    product = _create_product(services, unit_price=Decimal("1000"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "transfer", "amount": "1000"}]},
        headers=headers,
    )

    assert response.status_code == 422


def test_complete_without_warehouse_returns_409(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "1000"}]},
        headers=headers,
    )

    assert response.status_code == 409
    assert "bodega" in response.json()["detail"].lower()


def test_complete_without_open_cash_session_returns_409(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    services.inventory_service.create_warehouse(name="Principal")
    services.cash_register_service.create_register(name="Caja 1")  # sin abrir turno
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "1000"}]},
        headers=headers,
    )

    assert response.status_code == 409
    assert "turno" in response.json()["detail"].lower()


def test_complete_succeeds_and_matches_desktop_calculation(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, unit_price=Decimal("1000"), track_inventory=True)
    _stock_product(services, product.id, Decimal("10"))
    _open_cash_session(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "3"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "3000"}]},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert Decimal(body["total"]) == Decimal("3000")
    assert len(body["items"]) == 1
    assert Decimal(body["items"][0]["quantity"]) == Decimal("3")
    assert len(body["payments"]) == 1
    assert body["payments"][0]["payment_method"] == "cash"
    assert "unit_cost" not in body["items"][0]

    # Coincide exactamente con lo que vería el escritorio para la misma venta.
    desktop_view = services.sales_service.get_sale(body["id"])
    assert desktop_view.total == Decimal("3000")
    assert desktop_view.status.value == "completed"


def test_complete_creates_a_dispatch_order_like_the_desktop(
    seeded_user: int, services: _Services
) -> None:
    """Corrección crítica: una venta completada desde Android debe
    aparecer en Despacho igual que una venta completada desde el
    escritorio — réplica de la rama `else` de `SaleViewModel.complete_sale`
    (`create_order_from_sale`), antes ausente en esta API."""
    product = _create_product(services, unit_price=Decimal("1000"), track_inventory=True)
    _stock_product(services, product.id, Decimal("10"))
    _open_cash_session(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "3"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "3000"}]},
        headers=headers,
    )
    sale_id = response.json()["id"]

    cards = services.kitchen_service.list_dispatch_queue()

    assert len(cards) == 1
    assert cards[0].origin.value == "ventas"
    assert cards[0].sale_id == sale_id
    assert cards[0].is_paid is True
    assert cards[0].item_count == 1
    assert cards[0].total_units == 3


def test_complete_twice_does_not_duplicate_the_dispatch_order(
    seeded_user: int, services: _Services
) -> None:
    """Un reintento sobre el mismo carrito ya completado devuelve la misma
    venta (ver `test_complete_twice_returns_the_same_sale_without_duplicating`)
    y tampoco debe duplicar el pedido de Despacho — `create_order_from_sale`
    solo se llama la primera vez, dentro del `completion_lock`."""
    product = _create_product(services, unit_price=Decimal("1000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )
    payload = {"payments": [{"payment_method": "cash", "amount": "1000"}]}

    client.post(f"/api/v1/sales/drafts/{draft_id}/complete", json=payload, headers=headers)
    client.post(f"/api/v1/sales/drafts/{draft_id}/complete", json=payload, headers=headers)

    cards = services.kitchen_service.list_dispatch_queue()
    assert len(cards) == 1


def test_complete_deducts_inventory_exactly_like_desktop(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("10"))
    _open_cash_session(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "4"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "14000"}]},
        headers=headers,
    )

    assert response.status_code == 200
    remaining = services.inventory_service.get_total_available_quantity(product.id)
    assert remaining == Decimal("6")


def test_complete_registers_a_cash_movement(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("2000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    register = next(iter(services.cash_register_service.list_registers()))
    session_before = services.cash_register_service.get_open_session(register.id)
    assert session_before is not None
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "2000"}]},
        headers=headers,
    )

    assert response.status_code == 200
    expected = services.cash_register_service.calculate_expected_amount(session_before.id)
    assert expected == Decimal("2000")


def test_complete_twice_returns_the_same_sale_without_duplicating(
    seeded_user: int, services: _Services
) -> None:
    """La venta solo se finaliza una vez: una segunda solicitud sobre el
    mismo carrito (reintento de red, doble tap) devuelve la misma venta,
    sin crear una segunda."""
    product = _create_product(services, unit_price=Decimal("1000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )
    payload = {"payments": [{"payment_method": "cash", "amount": "1000"}]}

    first = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete", json=payload, headers=headers
    )
    second = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete", json=payload, headers=headers
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    recent = services.sales_service.list_recent_sales()
    assert len(recent) == 1


def test_complete_concurrently_on_the_same_draft_only_creates_one_sale(
    seeded_user: int, services: _Services
) -> None:
    """Dos solicitudes de finalización verdaderamente simultáneas para el
    MISMO carrito (no una tras otra) — el lock por carrito de
    `SaleDraftStore.completion_lock` debe serializarlas."""
    import concurrent.futures

    product = _create_product(services, unit_price=Decimal("1000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )
    payload = {"payments": [{"payment_method": "cash", "amount": "1000"}]}

    def _complete() -> int:
        response = client.post(
            f"/api/v1/sales/drafts/{draft_id}/complete", json=payload, headers=headers
        )
        assert response.status_code == 200
        return int(response.json()["id"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: _complete(), range(2)))

    assert results[0] == results[1]
    assert len(services.sales_service.list_recent_sales()) == 1


def test_cannot_modify_a_draft_after_it_was_completed(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "1000"}]},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )

    assert response.status_code == 409


def test_complete_with_insufficient_stock_leaves_no_partial_data(
    seeded_user: int, services: _Services
) -> None:
    """Si `complete_sale` falla (acá, porque el stock se agotó entre
    agregar al carrito y cobrar), no debe quedar ninguna venta ni
    movimiento de inventario a medio camino."""
    product = _create_product(services, track_inventory=True)
    _stock_product(services, product.id, Decimal("5"))
    _open_cash_session(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "5"},
        headers=headers,
    )
    # El stock se agota por otra vía (ej. otra estación) después de armar
    # el carrito, antes de cobrar — `complete_sale` debe rechazarlo igual
    # que rechazaría al escritorio en el mismo escenario.
    other_warehouse = services.inventory_service.create_warehouse(name="Otra bodega")
    services.inventory_service.register_exit(
        product_id=product.id,
        warehouse_id=next(
            w.id for w in services.inventory_service.list_warehouses() if w.name == "Principal"
        ),
        quantity=Decimal("4"),
        reason="Prueba: vender casi todo el stock por otra vía",
        created_by_user_id=None,
    )
    assert other_warehouse.name == "Otra bodega"

    response = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "5000"}]},
        headers=headers,
    )

    assert response.status_code == 422
    assert services.sales_service.list_recent_sales() == []
    assert services.inventory_service.get_total_available_quantity(product.id) == Decimal("1")

    # El carrito sigue disponible para reintentar (no quedó marcado como
    # completado por un intento fallido).
    get_response = client.get(f"/api/v1/sales/drafts/{draft_id}", headers=headers)
    assert get_response.status_code == 200


# -- Fase 4: consultar una venta finalizada -----------------------------------


def test_get_sale_by_id(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
    client.post(
        f"/api/v1/sales/drafts/{draft_id}/items",
        json={"product_id": product.id, "quantity": "1"},
        headers=headers,
    )
    sale_id = client.post(
        f"/api/v1/sales/drafts/{draft_id}/complete",
        json={"payments": [{"payment_method": "cash", "amount": "1000"}]},
        headers=headers,
    ).json()["id"]

    response = client.get(f"/api/v1/sales/{sale_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == sale_id
    assert response.json()["total"] == "1000.00"


def test_get_unknown_sale_returns_404(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)
    headers = _login_headers(client)

    response = client.get("/api/v1/sales/999999", headers=headers)

    assert response.status_code == 404


def test_get_sale_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/sales/1")

    assert response.status_code == 401


# -- Historial (lista de ventas recientes) ------------------------------------


def test_list_sales_requires_authentication(seeded_user: int, services: _Services) -> None:
    client = _make_client(services)

    response = client.get("/api/v1/sales")

    assert response.status_code == 401


def test_list_sales_requires_sales_create_permission(
    seeded_non_admin_user: int, services: _Services
) -> None:
    client = _make_client(services)
    headers = _login_headers(client, username="mesero_no_admin")

    response = client.get("/api/v1/sales", headers=headers)

    assert response.status_code == 403


def test_list_sales_returns_recent_sales_most_recent_first(
    seeded_user: int, services: _Services
) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)

    sale_ids = []
    for _ in range(2):
        draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
        client.post(
            f"/api/v1/sales/drafts/{draft_id}/items",
            json={"product_id": product.id, "quantity": "1"},
            headers=headers,
        )
        sale_id = client.post(
            f"/api/v1/sales/drafts/{draft_id}/complete",
            json={"payments": [{"payment_method": "cash", "amount": "1000"}]},
            headers=headers,
        ).json()["id"]
        sale_ids.append(sale_id)

    response = client.get("/api/v1/sales", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert [sale["id"] for sale in body] == list(reversed(sale_ids))


def test_list_sales_respects_the_limit_query_param(seeded_user: int, services: _Services) -> None:
    product = _create_product(services, unit_price=Decimal("1000"))
    _ready_for_checkout(services, opened_by_user_id=seeded_user)
    client = _make_client(services)
    headers = _login_headers(client)
    for _ in range(3):
        draft_id = client.post("/api/v1/sales/drafts", headers=headers).json()["draft_id"]
        client.post(
            f"/api/v1/sales/drafts/{draft_id}/items",
            json={"product_id": product.id, "quantity": "1"},
            headers=headers,
        )
        client.post(
            f"/api/v1/sales/drafts/{draft_id}/complete",
            json={"payments": [{"payment_method": "cash", "amount": "1000"}]},
            headers=headers,
        )

    response = client.get("/api/v1/sales?limit=1", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
