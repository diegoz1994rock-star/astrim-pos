"""Diálogo de creación de cliente."""

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


class CustomerFormDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo cliente")

        self._full_name_edit = QLineEdit(self)
        self._document_id_edit = QLineEdit(self)
        self._email_edit = QLineEdit(self)
        self._phone_edit = QLineEdit(self)
        self._address_edit = QLineEdit(self)
        self._credit_limit_edit = QLineEdit(self)
        self._credit_limit_edit.setText("0")

        form = QFormLayout(self)
        form.addRow("Nombre completo", self._full_name_edit)
        form.addRow("Documento (opcional)", self._document_id_edit)
        form.addRow("Correo (opcional)", self._email_edit)
        form.addRow("Teléfono (opcional)", self._phone_edit)
        form.addRow("Dirección (opcional)", self._address_edit)
        form.addRow("Cupo de crédito", self._credit_limit_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._values: dict[str, object] | None = None

    def _on_accept(self) -> None:
        try:
            credit_limit = Decimal(self._credit_limit_edit.text() or "0")
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "El cupo de crédito debe ser un número válido.")
            return

        self._values = {
            "full_name": self._full_name_edit.text().strip(),
            "document_id": self._document_id_edit.text().strip() or None,
            "email": self._email_edit.text().strip() or None,
            "phone": self._phone_edit.text().strip() or None,
            "address": self._address_edit.text().strip() or None,
            "credit_limit": credit_limit,
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
