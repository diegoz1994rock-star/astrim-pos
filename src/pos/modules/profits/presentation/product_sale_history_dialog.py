"""Diálogo de historial de ventas de un producto — se abre al hacer doble
clic sobre una fila de la tabla principal de Ganancias. Muestra cada venta
individual (factura, cliente, usuario, caja, fecha/hora, cantidad, costo y
precio históricos, ganancia de esa línea) dentro del período/filtros
actuales de la pestaña."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pos.modules.profits.application.dto import ProductSaleHistoryEntryDTO
from pos.modules.profits.application.export_formatting import format_quantity
from pos.shared_ui.formatting import format_currency

_NA = "N/D"
_COLUMNS = [
    "Venta",
    "Factura",
    "Cliente",
    "Usuario",
    "Caja",
    "Fecha y hora",
    "Cantidad",
    "Costo histórico",
    "Precio histórico",
    "Ganancia",
]


class ProductSaleHistoryDialog(QDialog):
    def __init__(self, product_name: str, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setWindowTitle(f"Historial de ventas — {product_name}")
        self.resize(900, 500)

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def set_entries(self, entries: list[ProductSaleHistoryEntryDTO]) -> None:
        self._table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            values = [
                f"#{entry.sale_id}",
                entry.invoice_number or "—",
                entry.customer_name,
                entry.user_name,
                entry.cash_register_name,
                entry.sold_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                format_quantity(entry.quantity, entry.sale_unit),
                _NA if entry.unit_cost is None else format_currency(entry.unit_cost),
                format_currency(entry.unit_price),
                _NA if entry.line_profit is None else format_currency(entry.line_profit),
            ]
            for col_index, value in enumerate(values):
                self._table.setItem(row_index, col_index, QTableWidgetItem(value))
