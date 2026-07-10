"""Diálogo de creación de proveedor."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QWidget


class SupplierFormDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo proveedor")

        self._company_name_edit = QLineEdit(self)
        self._contact_name_edit = QLineEdit(self)
        self._document_id_edit = QLineEdit(self)
        self._email_edit = QLineEdit(self)
        self._phone_edit = QLineEdit(self)
        self._address_edit = QLineEdit(self)

        form = QFormLayout(self)
        form.addRow("Razón social", self._company_name_edit)
        form.addRow("Contacto (opcional)", self._contact_name_edit)
        form.addRow("NIT/Documento (opcional)", self._document_id_edit)
        form.addRow("Correo (opcional)", self._email_edit)
        form.addRow("Teléfono (opcional)", self._phone_edit)
        form.addRow("Dirección (opcional)", self._address_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict[str, str | None]:
        return {
            "company_name": self._company_name_edit.text().strip(),
            "contact_name": self._contact_name_edit.text().strip() or None,
            "document_id": self._document_id_edit.text().strip() or None,
            "email": self._email_edit.text().strip() or None,
            "phone": self._phone_edit.text().strip() or None,
            "address": self._address_edit.text().strip() or None,
        }
