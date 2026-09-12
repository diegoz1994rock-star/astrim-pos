"""Pruebas de `RestaurantViewModel` con dependencias simuladas (`Mock`):
valida que Vendedor rechace agregar/editar cantidades por encima del
stock disponible, avisando de inmediato (sin esperar a Caja) — mismo
patrón que ya cubre `tests/ui/sales/test_sale_view_model.py` para
`SaleViewModel._check_stock`."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.inventory.application.dto import WarehouseDTO
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.restaurant.presentation.restaurant_view_model import RestaurantViewModel

_WAREHOUSE = WarehouseDTO(id=1, name="Principal", location=None, is_active=True)


def _product(product_id: int, track_inventory: bool = True) -> ProductDTO:
    return ProductDTO(
        id=product_id,
        sku=f"SKU-{product_id}",
        name=f"Producto {product_id}",
        description=None,
        category_id=None,
        category_name=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("100"),
        cost_price=Decimal("50"),
        unit_of_measure="unidades",
        is_active=True,
        track_inventory=track_inventory,
    )


def _make_view_model(
    products: list[ProductDTO] | None = None, available_quantity: Decimal = Decimal("1000")
) -> RestaurantViewModel:
    restaurant_service = Mock()
    product_service = Mock()
    category_service = Mock()
    inventory_service = Mock()
    inventory_service.list_warehouses.return_value = [_WAREHOUSE]
    inventory_service.get_total_available_quantity.return_value = available_quantity
    sales_service = Mock()
    sales_service.preview_sale.return_value = Mock()
    session_manager = Mock()
    view_model = RestaurantViewModel(
        restaurant_service,
        product_service,
        category_service,
        inventory_service,
        sales_service,
        session_manager,
        Mock(),  # scale_service
    )
    view_model._products = products if products is not None else []
    return view_model


def test_add_item_rejects_when_there_is_no_stock(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("0"))
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.add_item(product_id=1, quantity=Decimal("1"))

    assert view_model._items == []
    assert errors == ["No hay existencias disponibles para este producto."]


def test_add_item_rejects_quantity_above_available_stock(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("5"))
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.add_item(product_id=1, quantity=Decimal("8"))

    assert view_model._items == []
    assert errors == ["Solo hay 5 unidades disponibles en inventario."]


def test_add_item_accepts_quantity_within_available_stock(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))

    view_model.add_item(product_id=1, quantity=Decimal("20"))

    assert len(view_model._items) == 1


def test_add_item_twice_rejects_once_combined_quantity_exceeds_stock(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))
    view_model.add_item(product_id=1, quantity=Decimal("15"))

    errors = []
    view_model.error_occurred.connect(errors.append)
    view_model.add_item(product_id=1, quantity=Decimal("10"))

    assert view_model._items[0].quantity == Decimal("15")
    assert errors == ["Solo hay 20 unidades disponibles en inventario."]


def test_update_item_rejects_quantity_above_available_stock(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))
    view_model.add_item(product_id=1, quantity=Decimal("5"))
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.update_item(0, quantity=Decimal("25"), note=None)

    assert view_model._items[0].quantity == Decimal("5")
    assert errors == ["Solo hay 20 unidades disponibles en inventario."]


def test_update_item_allows_reducing_quantity_of_own_line(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))
    view_model.add_item(product_id=1, quantity=Decimal("20"))

    view_model.update_item(0, quantity=Decimal("10"), note=None)

    assert view_model._items[0].quantity == Decimal("10")


def test_add_item_ignores_stock_for_products_that_do_not_track_inventory(qtbot: QtBot) -> None:
    view_model = _make_view_model(
        products=[_product(1, track_inventory=False)], available_quantity=Decimal("0")
    )

    view_model.add_item(product_id=1, quantity=Decimal("999"))

    assert len(view_model._items) == 1


def test_confirm_order_passes_customer_name_and_document(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))
    view_model.add_item(product_id=1, quantity=Decimal("1"))
    view_model._restaurant_service.create_order.return_value = Mock(customer_name="Mario Gómez")

    view_model.confirm_order("Mario Gómez", "10203040")

    _, kwargs = view_model._restaurant_service.create_order.call_args
    assert kwargs["customer_name"] == "Mario Gómez"
    assert kwargs["customer_document"] == "10203040"
