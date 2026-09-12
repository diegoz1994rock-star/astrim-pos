"""Diálogo de creación/edición de un número de Nequi (Administración)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from pos.modules.nequi_payments.application.dto import NequiPaymentConfigDTO


class NequiPaymentConfigFormDialog(QDialog):
    def __init__(
        self,
        existing_config: NequiPaymentConfigDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            "Cambiar número de Nequi" if existing_config else "Añadir número de Nequi"
        )

        self._number_edit = QLineEdit(self)
        if existing_config is not None:
            self._number_edit.setText(existing_config.number)

        form = QFormLayout(self)
        form.addRow("Número de Nequi (ej. 3001234567)", self._number_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar número")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._values: dict[str, object] | None = None

    def _on_accept(self) -> None:
        number = self._number_edit.text().strip()
        if not number:
            QMessageBox.warning(self, "Error", "El número de Nequi es obligatorio.")
            return
        self._values = {"number": number}
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
