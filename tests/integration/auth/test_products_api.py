"""Pruebas de integración de la Fase 2 de la API HTTP de negocio (ASTRIM):
`GET /api/v1/categories`, `GET /api/v1/products` (+ búsqueda `?q=`),
`GET /api/v1/products/by-barcode/{code}` y `GET /api/v1/products/{id}` —
contra un `TestClient` real, con productos/categorías reales sembrados vía
los mismos `Service` que usa el escritorio (nunca INSERT directo).

Todas las rutas están protegidas por `AuthMiddleware` (Fase 1) — cada
prueba pasa primero por `/api/v1/auth/login` para obtener un token real,
igual que haría un cliente externo (Android)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

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
from pos.modules.products.domain.enums import ProductType, SaleUnit
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

_Services = tuple[ProductManagementService, CategoryManagementService]


@pytest.fixture
def product_and_category_services(sqlite_engine: None) -> _Services:
    """`ProductManagementService`/`CategoryManagementService` reales, contra
    la misma SQLite que ya inicializó `sqlite_engine` — se le pasan a
    `create_sync_app` en `_make_client()` (ver su docstring en `router.py`
    sobre por qué son parámetros explícitos y no se resuelven de un
    contenedor global)."""
    return ProductManagementService(EventBus()), CategoryManagementService()


def _make_client(services: _Services) -> TestClient:
    product_service, category_service = services
    event_bus = EventBus()
    settings = BusinessSettingsService(event_bus)
    sync_service = SyncService(event_bus, settings)
    auth_service = AuthenticationService(SessionManager(), event_bus)
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


def _login_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


# -- Categorías --------------------------------------------------------------


def test_list_categories_requires_authentication(
    seeded_user: int, product_and_category_services: _Services
) -> None:
    client = _make_client(product_and_category_services)

    response = client.get("/api/v1/categories")

    assert response.status_code == 401


def test_list_categories_returns_the_seeded_categories(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    _product_service, category_service = product_and_category_services
    category_service.create_category(name="Bebidas")
    category_service.create_category(name="Snacks")
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/categories", headers=headers)

    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert names == {"Bebidas", "Snacks"}


# -- Productos: listado y búsqueda -------------------------------------------


def test_list_products_requires_authentication(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    client = _make_client(product_and_category_services)

    response = client.get("/api/v1/products")

    assert response.status_code == 401


def test_list_products_returns_products_without_cost_price(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Coca-Cola 400ml"
    assert body[0]["unit_price"] == "3500.00"
    assert "cost_price" not in body[0]


def test_search_products_by_name_matches_desktop_search_semantics(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    """Mismo criterio que `SearchFilterProxyModel` del escritorio:
    subcadena, sin distinguir mayúsculas/minúsculas."""
    product_service, _category_service = product_and_category_services
    product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    product_service.create_product(
        sku="SKU-2",
        name="Papa criolla",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("6000"),
        cost_price=Decimal("3000"),
        unit_of_measure="kg",
        track_inventory=True,
        sale_unit=SaleUnit.WEIGHT,
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products", params={"q": "coca"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Coca-Cola 400ml"


def test_search_products_by_name_is_case_insensitive(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products", params={"q": "COCA-COLA"}, headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_search_products_with_no_match_returns_empty_list(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products", params={"q": "nada-que-coincida"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


# -- Productos: búsqueda por código de barras --------------------------------


def test_get_product_by_barcode(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product = product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    product_service.add_barcode(product.id, "7701234567890")
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products/by-barcode/7701234567890", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == product.id
    assert response.json()["barcodes"] == ["7701234567890"]


def test_get_product_by_unknown_barcode_returns_404(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products/by-barcode/no-existe", headers=headers)

    assert response.status_code == 404


# -- Productos: detalle por id ------------------------------------------------


def test_get_product_by_id_returns_full_detail_for_simple_product(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, category_service = product_and_category_services
    category = category_service.create_category(name="Bebidas")
    product = product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description="Bebida gaseosa",
        category_id=category.id,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/products/{product.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "Bebida gaseosa"
    assert body["category_name"] == "Bebidas"
    assert body["recipe_items"] == []
    assert body["combo_items"] == []
    assert "cost_price" not in body


def test_get_product_by_id_includes_recipe_items_for_compound_product(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    ingredient = product_service.create_product(
        sku="HARINA",
        name="Harina",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("1000"),
        cost_price=Decimal("500"),
        unit_of_measure="kg",
        track_inventory=True,
    )
    dish = product_service.create_product(
        sku="AREPA",
        name="Arepa",
        description=None,
        category_id=None,
        product_type=ProductType.COMPOUND,
        unit_price=Decimal("2000"),
        cost_price=Decimal("800"),
        unit_of_measure="unidad",
        track_inventory=False,
    )
    product_service.add_recipe_item(
        recipe_product_id=dish.id,
        ingredient_product_id=ingredient.id,
        quantity=Decimal("0.1"),
        unit_of_measure="kg",
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/products/{dish.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["recipe_items"]) == 1
    assert body["recipe_items"][0]["ingredient_name"] == "Harina"
    assert body["recipe_items"][0]["quantity"] == "0.100"


def test_get_product_by_id_includes_combo_items_for_combo_product(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    component = product_service.create_product(
        sku="HAMBURGUESA",
        name="Hamburguesa",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("8000"),
        cost_price=Decimal("4000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    combo = product_service.create_product(
        sku="COMBO-1",
        name="Combo Hamburguesa",
        description=None,
        category_id=None,
        product_type=ProductType.COMBO,
        unit_price=Decimal("12000"),
        cost_price=Decimal("6000"),
        unit_of_measure="unidad",
        track_inventory=False,
    )
    product_service.add_combo_item(
        combo_product_id=combo.id, product_id=component.id, quantity=Decimal("1")
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/products/{combo.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["combo_items"]) == 1
    assert body["combo_items"][0]["product_name"] == "Hamburguesa"


def test_get_product_by_unknown_id_returns_404(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products/999999", headers=headers)

    assert response.status_code == 404


# -- Productos: imagen (Fase 2 Android) ---------------------------------------


def test_get_product_image_requires_authentication(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product = product_service.create_product(
        sku="SKU-1", name="Coca-Cola 400ml", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=True,
    )
    client = _make_client(product_and_category_services)

    response = client.get(f"/api/v1/products/{product.id}/image")

    assert response.status_code == 401


def test_get_product_image_returns_404_for_unknown_id(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products/999999/image", headers=headers)

    assert response.status_code == 404


def test_get_product_image_returns_404_when_product_has_no_image(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product = product_service.create_product(
        sku="SKU-1", name="Coca-Cola 400ml", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=True,
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/products/{product.id}/image", headers=headers)

    assert response.status_code == 404


def test_get_product_image_returns_404_when_file_is_missing_on_disk(
    seeded_user: int,
    product_and_category_services: _Services,
    tmp_path: Path,
) -> None:
    """`image_path` puede apuntar a un archivo que ya no existe (borrado a
    mano, respaldo restaurado sin las imágenes, etc.) — no debe reventar con
    un 500, se trata igual que "no tiene imagen"."""
    product_service, _category_service = product_and_category_services
    product = product_service.create_product(
        sku="SKU-1", name="Coca-Cola 400ml", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=True,
    )
    product_service.update_product(
        product.id, sku="SKU-1", name="Coca-Cola 400ml", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=True,
        image_path=str(tmp_path / "no-existe.jpg"),
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/products/{product.id}/image", headers=headers)

    assert response.status_code == 404


def test_get_product_image_returns_the_file_bytes(
    seeded_user: int,
    product_and_category_services: _Services,
    tmp_path: Path,
) -> None:
    product_service, _category_service = product_and_category_services
    product = product_service.create_product(
        sku="SKU-1", name="Coca-Cola 400ml", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=True,
    )
    image_file = tmp_path / "producto.jpg"
    image_file.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    product_service.update_product(
        product.id, sku="SKU-1", name="Coca-Cola 400ml", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=True,
        image_path=str(image_file),
    )
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get(f"/api/v1/products/{product.id}/image", headers=headers)

    assert response.status_code == 200
    assert response.content == b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    assert response.headers["content-type"] == "image/jpeg"


def test_get_product_by_id_requires_authentication(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product = product_service.create_product(
        sku="SKU-1",
        name="Coca-Cola 400ml",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    client = _make_client(product_and_category_services)

    response = client.get(f"/api/v1/products/{product.id}")

    assert response.status_code == 401


# -- Fase 5: paginación (retrocompatible) ------------------------------------


def _seed_products(services: _Services, count: int) -> None:
    product_service, _category_service = services
    for i in range(count):
        product_service.create_product(
            sku=f"SKU-{i:03d}",
            name=f"Producto {i:03d}",
            description=None,
            category_id=None,
            product_type=ProductType.SIMPLE,
            unit_price=Decimal("1000"),
            cost_price=Decimal("500"),
            unit_of_measure="unidad",
            track_inventory=False,
        )


def test_list_products_without_pagination_params_returns_everything(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    """Comportamiento sin cambios respecto a la Fase 2: sin `?limit`/
    `?offset`, sigue devolviendo la lista completa."""
    _seed_products(product_and_category_services, 12)
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 12
    assert response.headers["X-Total-Count"] == "12"


def test_list_products_with_limit_returns_a_page(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    _seed_products(product_and_category_services, 12)
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products", params={"limit": 5}, headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 5
    assert response.headers["X-Total-Count"] == "12"


def test_list_products_with_limit_and_offset_pages_through_all_results(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    _seed_products(product_and_category_services, 12)
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    first_page = client.get(
        "/api/v1/products", params={"limit": 5, "offset": 0}, headers=headers
    ).json()
    second_page = client.get(
        "/api/v1/products", params={"limit": 5, "offset": 5}, headers=headers
    ).json()
    third_page = client.get(
        "/api/v1/products", params={"limit": 5, "offset": 10}, headers=headers
    ).json()

    assert len(first_page) == 5
    assert len(second_page) == 5
    assert len(third_page) == 2
    all_skus = {p["sku"] for p in first_page + second_page + third_page}
    assert len(all_skus) == 12  # sin repetidos ni faltantes


def test_list_products_pagination_combines_with_search(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    product_service, _category_service = product_and_category_services
    product_service.create_product(
        sku="COCA-1", name="Coca-Cola", description=None, category_id=None,
        product_type=ProductType.SIMPLE, unit_price=Decimal("3500"), cost_price=Decimal("2000"),
        unit_of_measure="unidad", track_inventory=False,
    )
    _seed_products(product_and_category_services, 5)
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get(
        "/api/v1/products", params={"q": "coca", "limit": 10}, headers=headers
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["X-Total-Count"] == "1"


def test_list_products_with_invalid_limit_returns_422(
    seeded_user: int,
    product_and_category_services: _Services,
) -> None:
    client = _make_client(product_and_category_services)
    headers = _login_headers(client)

    response = client.get("/api/v1/products", params={"limit": 0}, headers=headers)

    assert response.status_code == 422
