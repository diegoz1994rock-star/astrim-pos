"""Modelos de tabla de Ganancias — `QAbstractTableModel` real (mismo
patrón que `products/presentation/products_table_model.py`) para que el
buscador use `QSortFilterProxyModel` de verdad y las columnas sean
ordenables de forma nativa (`QTableView.setSortingEnabled(True)`)."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from pos.modules.profits.application.dto import CategoryProfitGroupDTO, ProductProfitRowDTO
from pos.modules.profits.application.export_formatting import (
    MARGIN_COLUMN_INDEX,
    PRODUCT_ROW_COLUMNS,
    format_quantity,
    product_row_to_strings,
)
from pos.modules.profits.domain.enums import MarginTier
from pos.modules.profits.domain.margin_tier import classify_margin
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.search_filter_proxy_model import SEARCH_ROLE

_NA = "N/D"


def _margin_color(tier: MarginTier) -> QColor:
    """Antes eran 4 colores hex hardcodeados en este archivo, ninguno
    exactamente igual a los tokens semánticos que ya existían (y no
    reactivos a un cambio de tema) — ver DESIGN_SYSTEM.md §1.3/§12."""
    tokens = get_active_tokens()
    return {
        MarginTier.HIGH: QColor(tokens.success),
        MarginTier.MEDIUM: QColor(tokens.warning),
        MarginTier.LOW: QColor(tokens.danger),
        MarginTier.NONE: QColor(tokens.text_secondary),
    }[tier]


COLUMNS = PRODUCT_ROW_COLUMNS


def _money(value) -> str:  # noqa: ANN001
    return _NA if value is None else format_currency(value)


class ProfitProductTableModel(QAbstractTableModel):
    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._rows: list[ProductProfitRowDTO] = []

    def set_rows(self, rows: list[ProductProfitRowDTO]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, row: int) -> ProductProfitRowDTO:
        return self._rows[row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

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
        row = self._rows[index.row()]
        column = index.column()

        if role == SEARCH_ROLE and column == 0:
            return " ".join([row.code, row.product_name, row.category_name, row.supplier_name])
        if role == Qt.ItemDataRole.TextAlignmentRole and column > 2:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ForegroundRole and column == MARGIN_COLUMN_INDEX:
            tier = classify_margin(row.margin_pct)
            return _margin_color(tier)
        if role == Qt.ItemDataRole.DisplayRole:
            return product_row_to_strings(row)[column]
        return None


CATEGORY_COLUMNS = ["Categoría", "Cantidad", "Ingresos", "Costos", "Ganancia"]


class CategoryProfitTableModel(QAbstractTableModel):
    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._rows: list[CategoryProfitGroupDTO] = []

    def set_rows(self, rows: list[CategoryProfitGroupDTO]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(CATEGORY_COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return CATEGORY_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.TextAlignmentRole and column > 0:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.DisplayRole:
            values = [
                row.category_name,
                format_quantity(row.quantity_sold, None),
                format_currency(row.total_revenue),
                _money(row.total_cost),
                _money(row.total_profit),
            ]
            return values[column]
        return None
