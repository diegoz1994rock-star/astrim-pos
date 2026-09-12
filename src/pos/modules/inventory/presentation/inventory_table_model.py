"""Modelo de tabla de Existencias — mismo patrón que
`products/presentation/products_table_model.py` (`QAbstractTableModel` +
`QSortFilterProxyModel` real). Los códigos de barras/categoría/imagen no
viven en `StockSummaryDTO`: se resuelven vía `product_lookup` contra la
lista de productos que la vista ya tiene cargada (mismo mecanismo que ya
usaba `InventoryView._product_by_id` para la imagen) — evita un join con
fan-out sobre la consulta agregada de existencias (`SUM` por bodega) y
reutiliza datos que de todas formas ya están en memoria."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from pos.modules.inventory.application.dto import StockSummaryDTO
from pos.modules.inventory.domain.enums import StockStatus
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.presentation.products_table_model import barcode_display
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.search_filter_proxy_model import SEARCH_ROLE
from pos.shared_ui.widgets.table_utils import make_image_icon

COLUMNS = ["Imagen", "SKU", "Código(s) de barras", "Producto", "Existencia Total", "Estado"]
IMAGE_SIZE = 128
"""Resolución del `QIcon` generado por `make_image_icon` — por encima del
tamaño real de despliegue en la celda (ver `ImageCellDelegate` en
`table_utils.py`, que la reescala él mismo) para que nunca haga falta
ampliar (perdería nitidez), solo reducir con `Qt.SmoothTransformation`."""

_STATUS_LABELS = {
    StockStatus.NORMAL: "Normal",
    StockStatus.LOW: "Stock Bajo",
    StockStatus.OUT: "Agotado",
}


def _status_color(status: StockStatus) -> QColor:
    """Antes eran 3 colores hex hardcodeados en este archivo (no
    reactivos a un cambio de tema) — ver DESIGN_SYSTEM.md §1.3/§12.
    Se resuelven en cada llamada, nunca al importar el módulo, para
    reflejar el tema activo en ese momento."""
    tokens = get_active_tokens()
    return {
        StockStatus.NORMAL: QColor(tokens.success_tint),
        StockStatus.LOW: QColor(tokens.warning_tint),
        StockStatus.OUT: QColor(tokens.danger_tint),
    }[status]


def _format_quantity(value: Decimal) -> str:
    """`quantity`/`min_quantity` se guardan como `Numeric(14, 3)` — un
    `str()` directo muestra siempre los 3 decimales (ej. "70.000"). Acá se
    recortan los ceros de más, mostrando "70" en vez de "70.000" pero
    conservando decimales reales como "12.5"."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class InventoryTableModel(QAbstractTableModel):
    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._summaries: list[StockSummaryDTO] = []
        self._product_lookup: Callable[[int], ProductDTO | None] = lambda _product_id: None

    def set_data(
        self,
        summaries: list[StockSummaryDTO],
        product_lookup: Callable[[int], ProductDTO | None],
    ) -> None:
        self.beginResetModel()
        self._summaries = summaries
        self._product_lookup = product_lookup
        self.endResetModel()

    def summary_at(self, row: int) -> StockSummaryDTO:
        return self._summaries[row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._summaries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        summary = self._summaries[index.row()]
        column = index.column()
        product = self._product_lookup(summary.product_id)

        if role == SEARCH_ROLE and column == 0:
            barcodes = product.barcodes if product is not None else ()
            category_name = (product.category_name if product is not None else None) or ""
            return " ".join(filter(None, [summary.sku, *barcodes, summary.name, category_name]))
        if role == Qt.ItemDataRole.DecorationRole and column == 0:
            image_path = product.image_path if product is not None else None
            return make_image_icon(image_path, IMAGE_SIZE)
        if role == Qt.ItemDataRole.TextAlignmentRole and column > 0:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.BackgroundRole and column > 0:
            return _status_color(summary.status)
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(summary, product, column)
        return None

    def _display_value(
        self, summary: StockSummaryDTO, product: ProductDTO | None, column: int
    ) -> str | None:
        if column == 1:
            return summary.sku
        if column == 2:
            return barcode_display(product.barcodes if product is not None else ())
        if column == 3:
            return summary.name
        if column == 4:
            return _format_quantity(summary.total_quantity)
        if column == 5:
            return _STATUS_LABELS[summary.status]
        return None
