"""Modelo de tabla de Productos — `QAbstractTableModel` real (no
`QTableWidget`) para que el buscador de Catálogo use `QSortFilterProxyModel`
de verdad, tal como se pidió, en vez de un filtro manual sobre celdas."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from pos.modules.products.application.dto import ProductDTO
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.widgets.search_filter_proxy_model import SEARCH_ROLE
from pos.shared_ui.widgets.table_utils import STATUS_ROLE_ROLE, make_image_icon

COLUMNS = [
    "Imagen",
    "SKU",
    "Código(s) de barras",
    "Nombre",
    "Categoría",
    "Tipo",
    "Precio",
    "Unidad de medida",
    "Estado",
]
IMAGE_SIZE = 128
"""Resolución del `QIcon` generado por `make_image_icon` — por encima del
tamaño real de despliegue en la celda (ver `ImageCellDelegate` en
`table_utils.py`, que la reescala él mismo) para que nunca haga falta
ampliar (perdería nitidez), solo reducir con `Qt.SmoothTransformation`."""


def barcode_display(barcodes: tuple[str, ...]) -> str:
    """Primer código si hay uno, `"N códigos"` si hay varios, `"—"` si no
    hay ninguno — misma regla en Catálogo e Inventario."""
    if not barcodes:
        return "—"
    if len(barcodes) == 1:
        return barcodes[0]
    return f"{len(barcodes)} códigos"


class ProductsTableModel(QAbstractTableModel):
    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._products: list[ProductDTO] = []

    def set_products(self, products: list[ProductDTO]) -> None:
        self.beginResetModel()
        self._products = products
        self.endResetModel()

    def product_at(self, row: int) -> ProductDTO:
        return self._products[row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._products)

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
        product = self._products[index.row()]
        column = index.column()

        if role == SEARCH_ROLE and column == 0:
            return " ".join(
                filter(
                    None,
                    [product.sku, *product.barcodes, product.name, product.category_name or ""],
                )
            )
        if role == Qt.ItemDataRole.DecorationRole and column == 0:
            return make_image_icon(product.image_path, IMAGE_SIZE)
        if role == Qt.ItemDataRole.TextAlignmentRole and column > 0:
            return Qt.AlignmentFlag.AlignCenter
        if role == STATUS_ROLE_ROLE and column == 8:
            return "success" if product.is_active else "secondary"
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(product, column)
        return None

    def _display_value(self, product: ProductDTO, column: int) -> str | None:
        if column == 1:
            return product.sku
        if column == 2:
            return barcode_display(product.barcodes)
        if column == 3:
            return product.name
        if column == 4:
            return product.category_name or ""
        if column == 5:
            return product.product_type.value
        if column == 6:
            return format_currency(product.unit_price)
        if column == 7:
            return product.unit_of_measure
        if column == 8:
            return "Activo" if product.is_active else "Inactivo"
        return None
