"""Diálogo de creación/edición de un impuesto."""

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

from pos.modules.taxes.application.dto import TaxDTO


class TaxFormDialog(QDialog):
    def __init__(
        self,
        existing_tax: TaxDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar impuesto" if existing_tax else "Nuevo impuesto")

        self._name_edit = QLineEdit(self)
        self._rate_edit = QLineEdit(self)
        if existing_tax is not None:
            self._name_edit.setText(existing_tax.name)
            self._rate_edit.setText(str(existing_tax.rate_percent))

        form = QFormLayout(self)
        form.addRow("Nombre", self._name_edit)
        form.addRow("Porcentaje", self._rate_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._values: dict[str, object] | None = None

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre del impuesto es obligatorio.")
            return
        try:
            rate_percent = Decimal(self._rate_edit.text())
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "El porcentaje debe ser un número válido.")
            return
        self._values = {"name": name, "rate_percent": rate_percent}
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
