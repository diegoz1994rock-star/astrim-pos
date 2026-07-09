"""Diálogo de creación de usuario."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from pos.modules.roles.application.dto import RoleDTO


class UserFormDialog(QDialog):
    """Formulario modal para crear un usuario nuevo."""

    def __init__(self, roles: list[RoleDTO], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo usuario")
        self._roles = roles

        self._username_edit = QLineEdit(self)
        self._password_edit = QLineEdit(self)
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._full_name_edit = QLineEdit(self)
        self._email_edit = QLineEdit(self)
        self._phone_edit = QLineEdit(self)
        self._role_combo = QComboBox(self)
        for role in roles:
            self._role_combo.addItem(role.name, userData=role.id)

        form = QFormLayout(self)
        form.addRow("Usuario", self._username_edit)
        form.addRow("Contraseña", self._password_edit)
        form.addRow("Nombre completo", self._full_name_edit)
        form.addRow("Correo (opcional)", self._email_edit)
        form.addRow("Teléfono (opcional)", self._phone_edit)
        form.addRow("Rol", self._role_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict[str, str | int]:
        """Datos ingresados, listos para pasar a `UsersViewModel.create_user`."""
        return {
            "username": self._username_edit.text().strip(),
            "password": self._password_edit.text(),
            "full_name": self._full_name_edit.text().strip(),
            "email": self._email_edit.text().strip(),
            "phone": self._phone_edit.text().strip(),
            "role_id": self._role_combo.currentData(),
        }
