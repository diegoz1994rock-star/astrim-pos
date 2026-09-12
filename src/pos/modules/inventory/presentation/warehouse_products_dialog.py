"""Diálogo de solo lectura: productos con existencia en una bodega
("Ver productos" en la pantalla de Bodegas). Solo se listan productos con
cantidad > 0 — a diferencia del detalle por producto, acá no tiene sentido
mostrar todo el catálogo con ceros."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.inventory.application.dto import StockLevelDTO

_COLUMNS = ["Producto", "Cantidad"]


def _format_quantity(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class WarehouseProductsDialog(QDialog):
    def __init__(
        self, warehouse_name: str, products: list[StockLevelDTO], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Productos en {warehouse_name}")

        layout = QVBoxLayout(self)
        header = QLabel(warehouse_name)
        header.setProperty("emphasis", True)
        layout.addWidget(header)

        table = QTableWidget(len(products), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, stock in enumerate(products):
            table.setItem(row, 0, QTableWidgetItem(stock.product_name))
            table.setItem(row, 1, QTableWidgetItem(_format_quantity(stock.quantity)))
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
