"""Diálogo de creación/edición de una caja registradora (punto de cobro)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from pos.modules.cash_register.application.dto import CashRegisterDTO


class CashRegisterFormDialog(QDialog):
    def __init__(
        self,
        existing_register: CashRegisterDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar caja" if existing_register else "Nueva caja")

        self._name_edit = QLineEdit(self)
        self._location_edit = QLineEdit(self)
        if existing_register is not None:
            self._name_edit.setText(existing_register.name)
            self._location_edit.setText(existing_register.location or "")

        form = QFormLayout(self)
        form.addRow("Nombre", self._name_edit)
        form.addRow("Ubicación (opcional)", self._location_edit)

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
            QMessageBox.warning(self, "Error", "El nombre de la caja es obligatorio.")
            return
        self._values = {
            "name": name,
            "location": self._location_edit.text().strip() or None,
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
