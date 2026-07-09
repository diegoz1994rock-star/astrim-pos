"""Pantalla de administración de roles y permisos: lista de roles + matriz
de permisos del rol seleccionado (checklist)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.modules.roles.application.dto import PermissionDTO, RoleDTO
from pos.modules.roles.presentation.roles_view_model import RolesViewModel


class RolesView(QWidget):
    """Vista de administración de roles y su matriz de permisos."""

    def __init__(self, view_model: RolesViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._roles: list[RoleDTO] = []
        self._permissions: list[PermissionDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        left_column = QVBoxLayout()
        roles_title = QLabel("Roles")
        roles_title_font = roles_title.font()
        roles_title_font.setBold(True)
        roles_title_font.setPointSize(14)
        roles_title.setFont(roles_title_font)
        left_column.addWidget(roles_title)

        self._roles_list = QListWidget(self)
        left_column.addWidget(self._roles_list)

        role_buttons = QHBoxLayout()
        self._new_role_button = QPushButton("Nuevo rol")
        self._delete_role_button = QPushButton("Eliminar rol")
        role_buttons.addWidget(self._new_role_button)
        role_buttons.addWidget(self._delete_role_button)
        left_column.addLayout(role_buttons)
        layout.addLayout(left_column, stretch=1)

        right_column = QVBoxLayout()
        permissions_title = QLabel("Permisos del rol seleccionado")
        permissions_title_font = permissions_title.font()
        permissions_title_font.setBold(True)
        permissions_title_font.setPointSize(14)
        permissions_title.setFont(permissions_title_font)
        right_column.addWidget(permissions_title)

        self._permissions_list = QListWidget(self)
        right_column.addWidget(self._permissions_list)

        self._save_permissions_button = QPushButton("Guardar permisos")
        right_column.addWidget(self._save_permissions_button)
        layout.addLayout(right_column, stretch=1)

    def _connect_signals(self) -> None:
        self._new_role_button.clicked.connect(self._on_new_role_clicked)
        self._delete_role_button.clicked.connect(self._on_delete_role_clicked)
        self._save_permissions_button.clicked.connect(self._on_save_permissions_clicked)
        self._roles_list.currentRowChanged.connect(self._on_role_selection_changed)
        self._view_model.roles_loaded.connect(self._on_roles_loaded)
        self._view_model.permissions_loaded.connect(self._on_permissions_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_permissions_loaded(self, permissions: list[PermissionDTO]) -> None:
        self._permissions = permissions

    def _on_roles_loaded(self, roles: list[RoleDTO]) -> None:
        self._roles = roles
        previous_row = self._roles_list.currentRow()
        self._roles_list.clear()
        for role in roles:
            self._roles_list.addItem(role.name)
        if 0 <= previous_row < len(roles):
            self._roles_list.setCurrentRow(previous_row)
        elif roles:
            self._roles_list.setCurrentRow(0)

    def _on_role_selection_changed(self, row: int) -> None:
        self._permissions_list.clear()
        if row < 0 or row >= len(self._roles):
            return
        role = self._roles[row]
        for permission in self._permissions:
            item = QListWidgetItem(permission.code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = permission.code in role.permission_codes
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self._permissions_list.addItem(item)

    def _selected_role(self) -> RoleDTO | None:
        row = self._roles_list.currentRow()
        if row < 0 or row >= len(self._roles):
            return None
        return self._roles[row]

    def _on_new_role_clicked(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nuevo rol", "Nombre del rol:")
        if accepted and name.strip():
            self._view_model.create_role(name.strip(), "", set())

    def _on_delete_role_clicked(self) -> None:
        role = self._selected_role()
        if role is None:
            self._show_error("Selecciona un rol de la lista.")
            return
        self._view_model.delete_role(role.id)

    def _on_save_permissions_clicked(self) -> None:
        role = self._selected_role()
        if role is None:
            self._show_error("Selecciona un rol de la lista.")
            return
        selected_codes = {
            self._permissions_list.item(i).text()
            for i in range(self._permissions_list.count())
            if self._permissions_list.item(i).checkState() == Qt.CheckState.Checked
        }
        self._view_model.update_permissions(role.id, selected_codes)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
