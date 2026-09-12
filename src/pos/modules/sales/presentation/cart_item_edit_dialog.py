"""Diálogo de edición de una línea del carrito de venta: solo permite
cambiar la cantidad y la nota. El precio lo define únicamente el
Administrador desde el Catálogo y no es editable aquí."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)


class CartItemEditDialog(QDialog):
    def __init__(
        self,
        product_name: str,
        quantity: Decimal,
        note: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Editar: {product_name}")

        self._quantity_edit = QLineEdit(str(quantity), self)
        self._note_edit = QLineEdit(note or "", self)

        form = QFormLayout(self)
        form.addRow("Cantidad", self._quantity_edit)
        form.addRow("Nota (opcional)", self._note_edit)

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
            "quantity": quantity,
            "note": self._note_edit.text().strip() or None,
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
