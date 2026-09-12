"""Diálogo de solo lectura: distribución de existencias de un producto por
bodega ("Ver" en la pantalla de Existencias). No permite modificar nada —
para eso están los diálogos de Entrada/Salida/Ajuste/Transferencia."""

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

_COLUMNS = ["Bodega", "Cantidad"]


def _format_quantity(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class StockDetailDialog(QDialog):
    def __init__(self, details: list[StockLevelDTO], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        product_name = details[0].product_name if details else ""
        sku = details[0].product_sku if details else ""
        self.setWindowTitle(f"Existencias: {product_name}")

        layout = QVBoxLayout(self)

        header = QLabel(f"Producto: {product_name}")
        header.setProperty("emphasis", True)
        layout.addWidget(header)
        layout.addWidget(QLabel(f"SKU: {sku}"))

        total = sum((detail.quantity for detail in details), Decimal(0))
        total_label = QLabel(f"Existencia Total: {_format_quantity(total)}")
        total_label.setProperty("emphasis", True)
        layout.addWidget(total_label)

        layout.addWidget(QLabel("Distribución por Bodega"))
        table = QTableWidget(len(details), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, detail in enumerate(details):
            table.setItem(row, 0, QTableWidgetItem(detail.warehouse_name))
            table.setItem(row, 1, QTableWidgetItem(_format_quantity(detail.quantity)))
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
