"""Diálogo de creación/edición de una llave Bre-B (Administración)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from pos.modules.bre_b_payments.application.dto import BreBPaymentConfigDTO


class BreBPaymentConfigFormDialog(QDialog):
    def __init__(
        self,
        existing_config: BreBPaymentConfigDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cambiar llave Bre-B" if existing_config else "Añadir llave Bre-B")

        self._key_edit = QLineEdit(self)
        if existing_config is not None:
            self._key_edit.setText(existing_config.key)

        form = QFormLayout(self)
        form.addRow("Llave Bre-B (celular, correo, documento o alfanumérica)", self._key_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar llave")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._values: dict[str, object] | None = None

    def _on_accept(self) -> None:
        key = self._key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Error", "La llave Bre-B es obligatoria.")
            return
        self._values = {"key": key}
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
