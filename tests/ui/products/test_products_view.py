"""Pruebas de UI de `ProductsView` (backend `offscreen`): la tabla pasó de
`QTableWidget` a `QTableView` + modelo + `QSortFilterProxyModel` para el
buscador en vivo — las aserciones leen los datos vía `view._source_model`/
`view._proxy_model` en vez de `.item()`/`.rowCount()`."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHeaderView
from pytestqt.qtbot import QtBot

from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.presentation.products_table_model import COLUMNS
from pos.modules.products.presentation.products_view import (
    _IMAGE_COLUMN_WIDTH,
    _ROW_HEIGHT,
    ProductsView,
)
from pos.shared_ui.widgets.table_utils import ImageCellDelegate

_MARTILLO = ProductDTO(
    id=1,
    sku="00001",
    name="Martillo 5K",
    description=None,
    category_id=1,
    category_name="Herramientas",
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("25000"),
    cost_price=Decimal("15000"),
    unit_of_measure="unidad",
    is_active=True,
    track_inventory=True,
    barcodes=("7701234567890",),
)
_DESTORNILLADOR = ProductDTO(
    id=2,
    sku="00002",
    name="Destornillador",
    description=None,
    category_id=1,
    category_name="Herramientas",
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("8000"),
    cost_price=Decimal("4000"),
    unit_of_measure="unidad",
    is_active=True,
    track_inventory=True,
    barcodes=("7709876543210", "7701111111111"),
)
_GASEOSA = ProductDTO(
    id=3,
    sku="00003",
    name="Gaseosa 1.5L",
    description=None,
    category_id=2,
    category_name="Bebidas",
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("5000"),
    cost_price=Decimal("3000"),
    unit_of_measure="unidad",
    is_active=True,
    track_inventory=True,
)


def _make_view(qtbot: QtBot) -> ProductsView:
    view = ProductsView(Mock())
    qtbot.addWidget(view)
    view._on_products_loaded([_MARTILLO, _DESTORNILLADOR, _GASEOSA])
    return view


def _cell(view: ProductsView, row: int, column_name: str) -> object:
    index = view._proxy_model.index(row, COLUMNS.index(column_name))
    return view._proxy_model.data(index, Qt.ItemDataRole.DisplayRole)


def test_table_shows_one_row_per_product(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert view._proxy_model.rowCount() == 3


def test_barcode_column_shows_single_code(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert _cell(view, 0, "Código(s) de barras") == "7701234567890"


def test_barcode_column_shows_count_for_multiple_codes(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert _cell(view, 1, "Código(s) de barras") == "2 códigos"


def test_barcode_column_shows_placeholder_when_no_barcodes(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert _cell(view, 2, "Código(s) de barras") == "—"


def test_search_by_name_filters_live(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._search_bar._edit.setText("martillo")

    assert view._proxy_model.rowCount() == 1
    assert _cell(view, 0, "Nombre") == "Martillo 5K"


def test_search_by_partial_name_matches_multiple_products(qtbot: QtBot) -> None:
    """"herra" no aparece en ningún nombre — solo en la categoría
    "Herramientas", que también forma parte del texto buscable."""
    view = _make_view(qtbot)

    view._search_bar._edit.setText("herra")

    assert view._proxy_model.rowCount() == 2


def test_search_by_sku_filters_live(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._search_bar._edit.setText("00002")

    assert view._proxy_model.rowCount() == 1
    assert _cell(view, 0, "SKU") == "00002"


def test_search_by_barcode_filters_live(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._search_bar._edit.setText("7701234567890")

    assert view._proxy_model.rowCount() == 1
    assert _cell(view, 0, "Nombre") == "Martillo 5K"


def test_clearing_search_shows_all_products_again(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._search_bar._edit.setText("martillo")
    assert view._proxy_model.rowCount() == 1

    view._search_bar._edit.setText("")

    assert view._proxy_model.rowCount() == 3


def test_ctrl_f_shortcut_is_wired_to_focus_search_bar(qtbot: QtBot) -> None:
    """`hasFocus()` real requiere activación de ventana a nivel de sistema
    operativo, poco confiable en el backend `offscreen` (límite de sandbox
    ya documentado) — se verifica la conexión disparando el `QShortcut`
    directamente y confirmando que llama a `SearchBar.focus()`."""
    view = _make_view(qtbot)
    view._search_bar._edit.setFocus = Mock()
    shortcuts = view.findChildren(QShortcut)
    ctrl_f = next(s for s in shortcuts if s.key() == QKeySequence.StandardKey.Find)

    ctrl_f.activated.emit()

    view._search_bar._edit.setFocus.assert_called_once()


def test_selecting_row_maps_through_proxy_to_correct_product(qtbot: QtBot) -> None:
    """El buscador reordena/oculta filas del proxy — seleccionar una fila
    filtrada debe resolver al producto correcto, no al de esa posición en
    la lista sin filtrar."""
    view = _make_view(qtbot)
    view._search_bar._edit.setText("destornillador")

    view._table.selectRow(0)

    assert view._selected_product() is _DESTORNILLADOR


# -- regresión: tamaño de la columna Imagen -------------------------------


def test_image_column_has_fixed_resize_mode(qtbot: QtBot) -> None:
    """Root cause de la regresión: sin esto, agregar/quitar columnas
    redistribuye el ancho de "Imagen" junto con las demás."""
    view = _make_view(qtbot)
    image_column = COLUMNS.index("Imagen")

    mode = view._table.horizontalHeader().sectionResizeMode(image_column)

    assert mode == QHeaderView.ResizeMode.Fixed


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


def test_other_columns_do_not_use_image_cell_delegate(qtbot: QtBot) -> None:
    """"Solamente ajustar el ancho de Imagen" — ninguna otra columna debe
    verse afectada por este delegado. La columna "Estado" tiene su propio
    `StatusChipDelegate`, ajeno a esta regla — solo importa que ninguna
    columna use el delegado de imagen fuera de "Imagen"."""
    view = _make_view(qtbot)
    image_column = COLUMNS.index("Imagen")

    for column in range(len(COLUMNS)):
        if column == image_column:
            continue
        assert not isinstance(view._table.itemDelegateForColumn(column), ImageCellDelegate)


def test_row_height_gives_the_image_room_to_breathe(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert view._table.verticalHeader().defaultSectionSize() == _ROW_HEIGHT
    assert _ROW_HEIGHT > 84  # más alto que antes de la corrección


def test_image_column_width_survives_reload(qtbot: QtBot) -> None:
    """`resizeColumnsToContents()` corre en cada recarga — el ancho fijo
    debe imponerse después, sin importar cuántas veces se repita."""
    view = _make_view(qtbot)
    image_column = COLUMNS.index("Imagen")

    view._on_products_loaded([_MARTILLO, _DESTORNILLADOR, _GASEOSA])
    view._on_products_loaded([_MARTILLO])

    assert view._table.columnWidth(image_column) == _IMAGE_COLUMN_WIDTH
