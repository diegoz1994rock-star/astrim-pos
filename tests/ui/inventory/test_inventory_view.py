"""Pruebas de UI de `InventoryView` (backend `offscreen`): una fila por
producto (existencia total + estado), doble clic abre el detalle por
bodega, y "Movimientos" abre el historial — sin diálogos bloqueantes reales
(se reemplazan por dobles livianos, mismo patrón ya usado en otras vistas).

Desde que la tabla pasó de `QTableWidget` a `QTableView` + modelo +
`QSortFilterProxyModel` (buscador en vivo), las aserciones leen los datos
vía `view._source_model`/`view._proxy_model` en vez de `.item()`/
`.cellWidget()`/`.rowCount()` (APIs exclusivas de `QTableWidget`)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView
from pytestqt.qtbot import QtBot

from pos.modules.inventory.application.dto import (
    StockLevelDTO,
    StockMovementDTO,
    StockSummaryDTO,
)
from pos.modules.inventory.domain.enums import StockMovementType, StockStatus
from pos.modules.inventory.presentation import inventory_view as inventory_view_module
from pos.modules.inventory.presentation.inventory_table_model import COLUMNS
from pos.modules.inventory.presentation.inventory_view import (
    _IMAGE_COLUMN_WIDTH,
    _ROW_HEIGHT,
    InventoryView,
)
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.presentation.products_view import (
    _IMAGE_COLUMN_WIDTH as _PRODUCTS_IMAGE_COLUMN_WIDTH,
)
from pos.shared_ui.widgets.table_utils import ImageCellDelegate

_PRODUCT = ProductDTO(
    id=1,
    sku="VAR-12",
    name="Varilla 1/2",
    description=None,
    category_id=None,
    category_name=None,
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("5"),
    cost_price=Decimal("3"),
    unit_of_measure="unidad",
    is_active=True,
    track_inventory=True,
)

_SUMMARIES = [
    StockSummaryDTO(
        product_id=1,
        sku="0007",
        name="Varilla 1/2",
        total_quantity=Decimal("85"),
        min_quantity=Decimal("20"),
        status=StockStatus.NORMAL,
    ),
    StockSummaryDTO(
        product_id=2,
        sku="0002",
        name="Varilla 1/4",
        total_quantity=Decimal("0"),
        min_quantity=Decimal("20"),
        status=StockStatus.OUT,
    ),
]


def _make_view(qtbot: QtBot) -> InventoryView:
    view = InventoryView(Mock())
    qtbot.addWidget(view)
    view._on_products_loaded([_PRODUCT])
    view._on_summary_loaded(_SUMMARIES)
    return view


def _cell(view: InventoryView, row: int, column_name: str) -> object:
    index = view._proxy_model.index(row, COLUMNS.index(column_name))
    return view._proxy_model.data(index, Qt.ItemDataRole.DisplayRole)


def test_table_shows_one_row_per_product(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert view._proxy_model.rowCount() == 2
    assert _cell(view, 0, "SKU") == "0007"
    assert _cell(view, 0, "Producto") == "Varilla 1/2"
    assert _cell(view, 0, "Existencia Total") == "85"
    assert _cell(view, 0, "Estado") == "Normal"
    assert _cell(view, 1, "Estado") == "Agotado"


def test_table_headers_have_no_warehouse_column(qtbot: QtBot) -> None:
    _make_view(qtbot)

    assert COLUMNS == [
        "Imagen", "SKU", "Código(s) de barras", "Producto", "Existencia Total", "Estado",
    ]
    assert "Bodega" not in COLUMNS
    assert "Stock Mínimo" not in COLUMNS
    assert "Acciones" not in COLUMNS


def test_image_decoration_present_in_each_row(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    image_column = COLUMNS.index("Imagen")
    for row in (0, 1):
        index = view._proxy_model.index(row, image_column)
        icon = view._proxy_model.data(index, Qt.ItemDataRole.DecorationRole)
        assert icon is not None


def test_barcode_column_shows_placeholder_when_no_barcodes(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert _cell(view, 0, "Código(s) de barras") == "—"


def test_search_by_name_filters_live(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._search_bar._edit.setText("1/4")

    assert view._proxy_model.rowCount() == 1
    assert _cell(view, 0, "SKU") == "0002"


def test_clearing_search_shows_all_rows_again(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._search_bar._edit.setText("1/4")
    assert view._proxy_model.rowCount() == 1

    view._search_bar._edit.setText("")

    assert view._proxy_model.rowCount() == 2


def _index_at(view: InventoryView, row: int) -> object:
    return view._proxy_model.index(row, 0)


def test_double_click_row_still_opens_detail_without_ver_button(
    qtbot: QtBot, monkeypatch
) -> None:
    """La columna Acciones (con el botón "Ver") ya no se muestra, pero el
    detalle sigue accesible con doble clic — no se pierde funcionalidad."""
    view = _make_view(qtbot)
    view._view_model.get_stock_detail.return_value = []
    monkeypatch.setattr(
        inventory_view_module, "StockDetailDialog", lambda details, parent=None: Mock(exec=Mock())
    )

    view._on_table_double_clicked(_index_at(view, 0))

    view._view_model.get_stock_detail.assert_called_once_with(1)


def test_ver_button_opens_stock_detail_with_correct_product(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._view_model.get_stock_detail.return_value = [
        StockLevelDTO(
            product_id=1,
            product_name="Varilla 1/2",
            product_sku="0007",
            warehouse_id=1,
            warehouse_name="Bodega Principal",
            quantity=Decimal("85"),
            min_quantity=Decimal("20"),
            is_below_minimum=False,
        )
    ]
    opened_with = []
    monkeypatch.setattr(
        inventory_view_module,
        "StockDetailDialog",
        lambda details, parent=None: opened_with.append(details) or Mock(exec=Mock()),
    )

    view._open_stock_detail(1)

    view._view_model.get_stock_detail.assert_called_once_with(1)
    assert len(opened_with) == 1


def test_double_click_row_opens_stock_detail(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._view_model.get_stock_detail.return_value = []
    monkeypatch.setattr(
        inventory_view_module, "StockDetailDialog", lambda details, parent=None: Mock(exec=Mock())
    )

    view._on_table_double_clicked(_index_at(view, 1))

    view._view_model.get_stock_detail.assert_called_once_with(2)


def test_movements_button_calls_load_movements(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_movements_clicked()

    view._view_model.load_movements.assert_called_once()


def test_movements_loaded_opens_history_dialog(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    movement = StockMovementDTO(
        id=1,
        movement_type=StockMovementType.ENTRY,
        quantity=Decimal("10"),
        reason=None,
        created_at=None,
        product_id=1,
        product_name="Varilla 1/2",
        warehouse_id=1,
        warehouse_name="Bodega Principal",
    )
    opened = []
    monkeypatch.setattr(
        inventory_view_module,
        "MovementsHistoryDialog",
        lambda movements, resolver, parent=None: opened.append(movements) or Mock(exec=Mock()),
    )

    view._on_movements_loaded([movement])

    assert opened == [[movement]]


def test_open_movement_dialog_preselects_product_from_selected_row(
    qtbot: QtBot, monkeypatch
) -> None:
    view = _make_view(qtbot)
    view._table.selectRow(0)
    captured = {}

    class _FakeDialog:
        DialogCode = Mock(Accepted=1, Rejected=0)

        def __init__(self, mode, products, warehouses, preselected_product, parent):
            captured["preselected_product"] = preselected_product

        def exec(self):
            return 0

    monkeypatch.setattr(inventory_view_module, "MovementDialog", _FakeDialog)
    view._warehouses = [Mock()]

    from pos.modules.inventory.presentation.movement_dialog import MovementMode

    view._open_dialog(MovementMode.ENTRY)

    assert captured["preselected_product"] is _PRODUCT


# -- regresión: tamaño de la columna Imagen -------------------------------


def test_image_column_has_fixed_resize_mode(qtbot: QtBot) -> None:
    """Root cause de la regresión: con el encabezado en `Stretch` (modo
    de siempre para el resto de columnas), agregar una columna nueva
    reduce la proporción de "Imagen" junto con las demás — a menos que
    quede fijada aparte, como acá."""
    view = _make_view(qtbot)
    image_column = COLUMNS.index("Imagen")

    mode = view._table.horizontalHeader().sectionResizeMode(image_column)

    assert mode == QHeaderView.ResizeMode.Fixed


def test_other_columns_keep_stretch_resize_mode(qtbot: QtBot) -> None:
    """"Las demás columnas son las que pueden crecer o reducirse" —
    Stretch para todo lo que no sea Imagen, sin cambios."""
    view = _make_view(qtbot)
    image_column = COLUMNS.index("Imagen")

    for column in range(len(COLUMNS)):
        if column == image_column:
            continue
        mode = view._table.horizontalHeader().sectionResizeMode(column)
        assert mode == QHeaderView.ResizeMode.Stretch


def test_image_column_width_is_within_requested_range(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    image_column = COLUMNS.index("Imagen")

    width = view._table.columnWidth(image_column)

    assert 90 <= width <= 120
    assert width == _IMAGE_COLUMN_WIDTH


def test_image_column_uses_image_cell_delegate(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    image_column = COLUMNS.index("Imagen")

    delegate = view._table.itemDelegateForColumn(image_column)

    assert isinstance(delegate, ImageCellDelegate)


def test_row_height_gives_the_image_room_to_breathe(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert view._table.verticalHeader().defaultSectionSize() == _ROW_HEIGHT
    assert _ROW_HEIGHT > 84  # más alto que antes de la corrección


def test_both_screens_use_the_same_image_column_width(qtbot: QtBot) -> None:
    """"Ambas deben verse idénticas" (Catálogo → Productos e
    Inventario → Existencias)."""
    assert _IMAGE_COLUMN_WIDTH == _PRODUCTS_IMAGE_COLUMN_WIDTH
