"""Pruebas de `SaleViewModel` con dependencias simuladas (`Mock`): al
agregar un producto que ya está en el carrito, se suma la cantidad a esa
misma línea en vez de crear una línea duplicada."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.barcode_scanners.application.dto import BarcodeReadResultDTO
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource, BarcodeSymbology
from pos.modules.inventory.application.dto import WarehouseDTO
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.restaurant.application.dto import OrderDTO, OrderItemDTO
from pos.modules.restaurant.domain.enums import OrderItemStatus, OrderStatus, OrderType
from pos.modules.sales.presentation.sale_view_model import SaleViewModel

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
) -> SaleViewModel:
    sales_service = Mock()
    sales_service.preview_sale.return_value = Mock()
    inventory_service = Mock()
    inventory_service.list_warehouses.return_value = [_WAREHOUSE]
    inventory_service.get_total_available_quantity.return_value = available_quantity
    restaurant_service = Mock()
    restaurant_service.list_pending_payment_orders.return_value = []
    # Por defecto sin cajas registradas — `scan_barcode` (como
    # `complete_sale`) hace `next(iter(list_registers()), None)`, que
    # necesita algo iterable; las pruebas que sí necesiten una caja
    # concreta lo sobrescriben.
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = []
    view_model = SaleViewModel(
        sales_service,
        Mock(),  # product_service
        Mock(),  # customer_service
        inventory_service,
        cash_register_service,
        Mock(),  # session_manager
        Mock(),  # billing_service
        Mock(),  # receipt_printer
        Mock(),  # cash_drawer_service
        Mock(),  # qr_payment_service
        restaurant_service,
        Mock(),  # scale_service
        Mock(),  # nequi_payment_service
        Mock(),  # breb_payment_service
        Mock(),  # barcode_read_service
        Mock(),  # printer_service
    )
    view_model._products = products if products is not None else []
    return view_model


def test_add_item_twice_for_same_product_merges_quantity(qtbot: QtBot) -> None:
    view_model = _make_view_model()

    view_model.add_item(product_id=1, quantity=Decimal("2"))
    view_model.add_item(product_id=1, quantity=Decimal("3"))

    assert len(view_model._items) == 1
    assert view_model._items[0].quantity == Decimal("5")


def test_add_item_for_different_products_keeps_separate_lines(qtbot: QtBot) -> None:
    view_model = _make_view_model()

    view_model.add_item(product_id=1, quantity=Decimal("2"))
    view_model.add_item(product_id=2, quantity=Decimal("1"))

    assert len(view_model._items) == 2


def test_add_item_merge_preserves_existing_note_when_none_given(qtbot: QtBot) -> None:
    view_model = _make_view_model()

    view_model.add_item(product_id=1, quantity=Decimal("1"), note="Frágil")
    view_model.add_item(product_id=1, quantity=Decimal("1"))

    assert view_model._items[0].note == "Frágil"
    assert view_model._items[0].quantity == Decimal("2")


def test_update_item_sets_quantity_and_note_only(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    view_model.add_item(product_id=1, quantity=Decimal("1"))

    view_model.update_item(0, quantity=Decimal("4"), note="Frágil")

    item = view_model._items[0]
    assert item.quantity == Decimal("4")
    assert item.note == "Frágil"


def test_add_item_rejects_quantity_above_available_stock(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.add_item(product_id=1, quantity=Decimal("30"))

    assert view_model._items == []
    assert errors == ["Stock insuficiente. Disponibles: 20 unidades."]


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
    assert errors == ["Stock insuficiente. Disponibles: 20 unidades."]


def test_update_item_rejects_quantity_above_available_stock(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))
    view_model.add_item(product_id=1, quantity=Decimal("5"))
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.update_item(0, quantity=Decimal("25"), note=None)

    assert view_model._items[0].quantity == Decimal("5")
    assert errors == ["Stock insuficiente. Disponibles: 20 unidades."]


def test_update_item_allows_reducing_quantity_of_own_line(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)], available_quantity=Decimal("20"))
    view_model.add_item(product_id=1, quantity=Decimal("20"))

    view_model.update_item(0, quantity=Decimal("10"), note=None)

    assert view_model._items[0].quantity == Decimal("10")


def test_add_item_skips_stock_check_for_products_not_tracking_inventory(qtbot: QtBot) -> None:
    view_model = _make_view_model(
        products=[_product(1, track_inventory=False)], available_quantity=Decimal("0")
    )

    view_model.add_item(product_id=1, quantity=Decimal("100"))

    assert len(view_model._items) == 1


def _order(
    order_id: int, quantity: int, notes: str | None = None, customer_name: str | None = None
) -> OrderDTO:
    return OrderDTO(
        id=order_id,
        table_session_id=None,
        order_type=OrderType.QUICK,
        status=OrderStatus.PENDING,
        customer_name=customer_name,
        items=[
            OrderItemDTO(
                id=1,
                order_id=order_id,
                product_id=1,
                product_name="Producto 1",
                quantity=quantity,
                notes=notes,
                status=OrderItemStatus.PENDING,
            )
        ],
    )


def test_load_from_order_fills_cart_with_order_items(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])

    view_model.load_from_order(_order(42, 3, "sin sal"))

    assert len(view_model._items) == 1
    assert view_model._items[0].quantity == Decimal("3")
    assert view_model._items[0].note == "sin sal"


def test_complete_sale_links_order_after_loading_from_order(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])
    view_model.load_from_order(_order(42, 2))

    fake_sale = Mock()
    fake_sale.id = 999
    fake_sale.items = []
    view_model._sales_service.complete_sale.return_value = fake_sale
    view_model._cash_register_service.list_registers.return_value = [Mock(id=1)]
    view_model._cash_register_service.get_open_session.return_value = Mock(id=1)

    view_model.complete_sale()

    view_model._restaurant_service.link_order_to_sale.assert_called_once_with(42, 999)


def test_complete_sale_without_loaded_order_does_not_link(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])
    view_model.add_item(product_id=1, quantity=Decimal("1"))

    fake_sale = Mock()
    fake_sale.id = 999
    fake_sale.items = []
    view_model._sales_service.complete_sale.return_value = fake_sale
    view_model._cash_register_service.list_registers.return_value = [Mock(id=1)]
    view_model._cash_register_service.get_open_session.return_value = Mock(id=1)

    view_model.complete_sale()

    view_model._restaurant_service.link_order_to_sale.assert_not_called()


def test_complete_sale_without_loaded_order_creates_dispatch_order(qtbot: QtBot) -> None:
    """Flujo 2 (Ventas → Despacho automático): una venta creada directo en
    Ventas, sin pasar por un pedido de Vendedor, debe aparecer en Despacho
    sola — ver `RestaurantService.create_order_from_sale`."""
    view_model = _make_view_model(products=[_product(1)])
    view_model.add_item(product_id=1, quantity=Decimal("1"))

    fake_sale = Mock()
    fake_sale.id = 999
    fake_sale.items = []
    view_model._sales_service.complete_sale.return_value = fake_sale
    view_model._cash_register_service.list_registers.return_value = [Mock(id=1)]
    view_model._cash_register_service.get_open_session.return_value = Mock(id=1)

    view_model.complete_sale()

    view_model._restaurant_service.create_order_from_sale.assert_called_once()
    args, kwargs = view_model._restaurant_service.create_order_from_sale.call_args
    assert args[0] is fake_sale


def test_complete_sale_from_loaded_order_only_links_does_not_duplicate(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])
    view_model.load_from_order(_order(42, 2))

    fake_sale = Mock()
    fake_sale.id = 999
    fake_sale.items = []
    view_model._sales_service.complete_sale.return_value = fake_sale
    view_model._cash_register_service.list_registers.return_value = [Mock(id=1)]
    view_model._cash_register_service.get_open_session.return_value = Mock(id=1)

    view_model.complete_sale()

    view_model._restaurant_service.link_order_to_sale.assert_called_once_with(42, 999)
    view_model._restaurant_service.create_order_from_sale.assert_not_called()


def test_load_from_order_prefills_customer_fields(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])
    received: list[tuple[str, str]] = []
    view_model.customer_fields_loaded.connect(lambda name, doc: received.append((name, doc)))

    view_model.load_from_order(_order(42, 2, customer_name="Mario Gómez"))

    assert received[-1] == ("Mario Gómez", "")
    assert view_model._customer_name_text == "Mario Gómez"


def test_complete_sale_clears_customer_fields(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])
    view_model.add_item(product_id=1, quantity=Decimal("1"))
    view_model.set_customer_name("Mario Gómez")
    view_model.set_customer_document("10203040")

    fake_sale = Mock()
    fake_sale.id = 999
    fake_sale.items = []
    view_model._sales_service.complete_sale.return_value = fake_sale
    view_model._cash_register_service.list_registers.return_value = [Mock(id=1)]
    view_model._cash_register_service.get_open_session.return_value = Mock(id=1)

    view_model.complete_sale()

    kwargs = view_model._sales_service.complete_sale.call_args.kwargs
    assert kwargs["customer_name"] == "Mario Gómez"
    assert kwargs["customer_document"] == "10203040"
    assert view_model._customer_name_text == ""
    assert view_model._customer_document_text == ""


def test_hold_current_sale_snapshots_cart_and_clears_it(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])
    view_model.add_item(product_id=1, quantity=Decimal("2"))
    view_model.set_customer(7)
    held_events = []
    view_model.held_sales_changed.connect(held_events.append)

    view_model.hold_current_sale()

    assert view_model._items == []
    assert view_model._customer_id is None
    assert len(view_model._held_sales) == 1
    assert view_model._held_sales[0].item_count == 1
    assert view_model._held_sales[0].customer_id == 7
    assert held_events[-1][0].item_count == 1


def test_resume_held_sale_restores_cart_and_removes_from_held_list(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1), _product(2)])
    view_model.add_item(product_id=1, quantity=Decimal("2"))
    view_model.set_customer(7)
    view_model.hold_current_sale()
    view_model.add_item(product_id=2, quantity=Decimal("1"))

    view_model.resume_held_sale(0)

    assert view_model._held_sales == []
    assert view_model._customer_id == 7
    assert len(view_model._items) == 1
    assert view_model._items[0].product_id == 1
    assert view_model._items[0].quantity == Decimal("2")


def test_resume_held_sale_ignores_out_of_range_index(qtbot: QtBot) -> None:
    view_model = _make_view_model(products=[_product(1)])
    view_model.add_item(product_id=1, quantity=Decimal("1"))

    view_model.resume_held_sale(5)

    assert len(view_model._items) == 1


def _found_result(product: ProductDTO, code: str = "7701234567890") -> BarcodeReadResultDTO:
    return BarcodeReadResultDTO(
        code=code, symbology=BarcodeSymbology.EAN13, found=True, product=product,
        ignored=False, reason=None,
    )


def _not_found_result(code: str = "0000000000000") -> BarcodeReadResultDTO:
    return BarcodeReadResultDTO(
        code=code, symbology=BarcodeSymbology.UNKNOWN, found=False, product=None,
        ignored=False, reason=None,
    )


def _ignored_result(code: str = "0000000000000") -> BarcodeReadResultDTO:
    return BarcodeReadResultDTO(
        code=code, symbology=BarcodeSymbology.UNKNOWN, found=False, product=None,
        ignored=True, reason="Lectura duplicada (rebote del lector).",
    )


def test_scan_barcode_found_adds_one_unit(qtbot: QtBot) -> None:
    product = _product(1)
    view_model = _make_view_model(products=[product])
    view_model._barcode_read_service.resolve_scan.return_value = _found_result(product)

    view_model.scan_barcode("7701234567890")

    assert len(view_model._items) == 1
    assert view_model._items[0].product_id == 1
    assert view_model._items[0].quantity == Decimal(1)


def test_scan_barcode_found_twice_merges_quantity_martillo_example(qtbot: QtBot) -> None:
    """Ejemplo exacto del pedido: escanear el mismo producto tres veces
    seguidas deja una sola línea con cantidad 3, nunca tres líneas."""
    product = _product(1)
    view_model = _make_view_model(products=[product])
    view_model._barcode_read_service.resolve_scan.return_value = _found_result(product)

    view_model.scan_barcode("7701234567890")
    view_model.scan_barcode("7701234567890")
    view_model.scan_barcode("7701234567890")

    assert len(view_model._items) == 1
    assert view_model._items[0].quantity == Decimal(3)


def test_scan_barcode_found_for_weight_product_does_not_add_one_unit(
    qtbot: QtBot,
) -> None:
    """Un producto por peso (`sale_unit=WEIGHT`) escaneado NUNCA se agrega
    automáticamente como 1 unidad — eso sería un peso inventado. El
    ViewModel deja el carrito intacto y solo emite `scan_resolved`; la
    vista es quien abre `ScaleWeightDialog` y agrega el peso real (ver
    `sale_view.py::_on_scan_resolved`)."""
    weight_product = ProductDTO(
        id=9, sku="SKU-9", name="Queso", description=None, category_id=None,
        category_name=None, product_type=ProductType.SIMPLE, unit_price=Decimal("8000"),
        cost_price=Decimal("4000"), unit_of_measure="kg", is_active=True, track_inventory=False,
        sale_unit=SaleUnit.WEIGHT,
    )
    view_model = _make_view_model(products=[weight_product])
    view_model._barcode_read_service.resolve_scan.return_value = _found_result(
        weight_product, code="7709876543210"
    )

    view_model.scan_barcode("7709876543210")

    assert len(view_model._items) == 0


def test_scan_barcode_not_found_does_not_add_item(qtbot: QtBot) -> None:
    """El aviso de "no encontrado" es responsabilidad de la vista
    (`SaleView._on_scan_resolved`, que primero intenta la búsqueda manual
    por SKU/nombre antes de mostrar el error — punto 7 del pedido): el
    ViewModel solo emite `scan_resolved` con el resultado crudo del
    servicio, sin decidir por su cuenta ni emitir un error propio (eso
    duplicaría/adelantaría el aviso incluso cuando la vista sí encuentra
    el producto por SKU)."""
    view_model = _make_view_model()
    view_model._barcode_read_service.resolve_scan.return_value = _not_found_result("9999999999999")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.scan_barcode("9999999999999")

    assert view_model._items == []
    assert errors == []


def test_scan_barcode_ignored_does_not_add_item_or_emit_error(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    view_model._barcode_read_service.resolve_scan.return_value = _ignored_result()
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.scan_barcode("7701234567890")

    assert view_model._items == []
    assert errors == []


def test_scan_barcode_always_emits_scan_resolved(qtbot: QtBot) -> None:
    product = _product(1)
    view_model = _make_view_model(products=[product])
    result = _found_result(product)
    view_model._barcode_read_service.resolve_scan.return_value = result
    received = []
    view_model.scan_resolved.connect(received.append)

    view_model.scan_barcode("7701234567890")

    assert received == [result]


def test_scan_barcode_passes_user_and_cash_register_to_resolve_scan(qtbot: QtBot) -> None:
    product = _product(1)
    view_model = _make_view_model(products=[product])
    view_model._barcode_read_service.resolve_scan.return_value = _found_result(product)
    session = Mock(user_id=42, full_name="Diego")
    view_model._session_manager.current = session
    register = Mock(id=7)
    register.name = "Caja 1"
    """`Mock(name=...)` no funciona como se espera: ese kwarg nombra al
    mock mismo (para su repr), no fija el atributo `.name` — hay que
    asignarlo aparte."""
    view_model._cash_register_service.list_registers.return_value = [register]

    view_model.scan_barcode("7701234567890")

    view_model._barcode_read_service.resolve_scan.assert_called_once_with(
        "7701234567890",
        source=BarcodeReadSource.SALE,
        user_id=42,
        username="Diego",
        cash_register_id=7,
        cash_register_name="Caja 1",
    )
