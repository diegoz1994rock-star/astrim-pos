"""Diálogo genérico para registrar entradas, salidas, ajustes y
transferencias de inventario. Los campos visibles cambian según `mode`.

Si se pasa `preselected_product` (la fila de producto que el usuario ya
tenía seleccionada en la tabla de Existencias — una fila por producto, sin
bodega asociada), el producto queda fijo como texto en vez de un
desplegable editable; la bodega siempre se elige manualmente, ya que la
tabla de Existencias ya no representa una bodega específica por fila."""

from __future__ import annotations

import enum
from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
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
        preselected_product: ProductDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._preselected_product = preselected_product
        self.setWindowTitle(_TITLES[mode])

        form = QFormLayout(self)
        warehouse_label = "Bodega de origen" if mode is MovementMode.TRANSFER else "Bodega"

        self._product_combo: QComboBox | None = None
        if preselected_product is not None:
            form.addRow(
                "Producto",
                QLabel(f"{preselected_product.sku} — {preselected_product.name}"),
            )
        else:
            self._product_combo = QComboBox(self)
            for product in products:
                self._product_combo.addItem(f"{product.sku} — {product.name}", userData=product.id)
            form.addRow("Producto", self._product_combo)

        self._warehouse_combo = QComboBox(self)
        for warehouse in warehouses:
            self._warehouse_combo.addItem(warehouse.name, userData=warehouse.id)
        form.addRow(warehouse_label, self._warehouse_combo)

        self._destination_combo: QComboBox | None = None
        if mode is MovementMode.TRANSFER:
            self._destination_combo = QComboBox(self)
            for warehouse in warehouses:
                self._destination_combo.addItem(warehouse.name, userData=warehouse.id)

        self._quantity_edit = QLineEdit(self)
        quantity_label = "Cantidad correcta" if mode is MovementMode.ADJUSTMENT else "Cantidad"
        form.addRow(quantity_label, self._quantity_edit)

        self._reason_edit: QLineEdit | None = None
        if mode is MovementMode.TRANSFER:
            assert self._destination_combo is not None
            form.addRow("Bodega de destino", self._destination_combo)
        else:
            self._reason_edit = QLineEdit(self)
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
        if self._mode is MovementMode.ADJUSTMENT:
            if quantity < 0:
                QMessageBox.warning(self, "Error", "La cantidad no puede ser negativa.")
                return
        elif quantity <= 0:
            QMessageBox.warning(self, "Error", "La cantidad debe ser mayor que cero.")
            return

        if self._preselected_product is not None:
            product_id: object = self._preselected_product.id
        else:
            assert self._product_combo is not None
            product_id = self._product_combo.currentData()
        warehouse_id = self._warehouse_combo.currentData()

        self._values = {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "destination_warehouse_id": (
                self._destination_combo.currentData()
                if self._destination_combo is not None
                else None
            ),
            "quantity": quantity,
            "reason": self._reason_edit.text().strip() if self._reason_edit is not None else "",
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
