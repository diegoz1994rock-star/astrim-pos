"""Diálogo genérico para registrar entradas, salidas, ajustes y
transferencias de inventario. Los campos visibles cambian según `mode`."""

from __future__ import annotations

import enum
from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from pos.modules.inventory.application.dto import WarehouseDTO
from pos.modules.products.application.dto import ProductDTO


class MovementMode(enum.Enum):
    ENTRY = "entry"
    EXIT = "exit"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"


_TITLES = {
    MovementMode.ENTRY: "Registrar entrada",
    MovementMode.EXIT: "Registrar salida",
    MovementMode.ADJUSTMENT: "Registrar ajuste",
    MovementMode.TRANSFER: "Transferir entre bodegas",
}


class MovementDialog(QDialog):
    def __init__(
        self,
        mode: MovementMode,
        products: list[ProductDTO],
        warehouses: list[WarehouseDTO],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle(_TITLES[mode])

        self._product_combo = QComboBox(self)
        for product in products:
            self._product_combo.addItem(f"{product.sku} — {product.name}", userData=product.id)

        self._warehouse_combo = QComboBox(self)
        for warehouse in warehouses:
            self._warehouse_combo.addItem(warehouse.name, userData=warehouse.id)

        self._destination_combo = QComboBox(self)
        for warehouse in warehouses:
            self._destination_combo.addItem(warehouse.name, userData=warehouse.id)

        self._quantity_edit = QLineEdit(self)
        self._reason_edit = QLineEdit(self)

        self._direction_combo = QComboBox(self)
        self._direction_combo.addItem("Aumentar", userData=True)
        self._direction_combo.addItem("Disminuir", userData=False)

        form = QFormLayout(self)
        form.addRow("Producto", self._product_combo)
        warehouse_label = "Bodega de origen" if mode is MovementMode.TRANSFER else "Bodega"
        form.addRow(warehouse_label, self._warehouse_combo)
        if mode is MovementMode.TRANSFER:
            form.addRow("Bodega de destino", self._destination_combo)
        form.addRow("Cantidad", self._quantity_edit)
        if mode is MovementMode.ADJUSTMENT:
            form.addRow("Dirección", self._direction_combo)
        if mode is not MovementMode.TRANSFER:
            form.addRow("Motivo (opcional)", self._reason_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._values: dict[str, object] | None = None

    def _on_accept(self) -> None:
        try:
            quantity = Decimal(self._quantity_edit.text())
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "La cantidad debe ser un número válido.")
            return
        if quantity <= 0:
            QMessageBox.warning(self, "Error", "La cantidad debe ser mayor que cero.")
            return

        self._values = {
            "product_id": self._product_combo.currentData(),
            "warehouse_id": self._warehouse_combo.currentData(),
            "destination_warehouse_id": self._destination_combo.currentData(),
            "quantity": quantity,
            "reason": self._reason_edit.text().strip(),
            "increase": self._direction_combo.currentData(),
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
