"""Pantalla de administración de usuarios: tabla + alta + activar/desactivar."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.roles.application.dto import RoleDTO
from pos.modules.users.application.dto import UserDTO
from pos.modules.users.presentation.user_form_dialog import UserFormDialog
from pos.modules.users.presentation.users_view_model import UsersViewModel

_COLUMNS = ["Usuario", "Nombre completo", "Rol", "Estado", "Correo"]


class UsersView(QWidget):
    """Vista de administración de usuarios."""

    def __init__(self, view_model: UsersViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._roles: list[RoleDTO] = []
        self._users: list[UserDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        title = QLabel("Usuarios")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._new_user_button = QPushButton("Nuevo usuario")
        toolbar.addWidget(self._new_user_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._toggle_active_button = QPushButton("Activar/Desactivar seleccionado")
        actions.addWidget(self._toggle_active_button)
        actions.addStretch()
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_user_button.clicked.connect(self._on_new_user_clicked)
        self._toggle_active_button.clicked.connect(self._on_toggle_active_clicked)
        self._view_model.users_loaded.connect(self._on_users_loaded)
        self._view_model.roles_loaded.connect(self._on_roles_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_roles_loaded(self, roles: list[RoleDTO]) -> None:
        self._roles = roles

    def _on_users_loaded(self, users: list[UserDTO]) -> None:
        self._users = users
        self._table.setRowCount(len(users))
        for row, user in enumerate(users):
            self._table.setItem(row, 0, QTableWidgetItem(user.username))
            self._table.setItem(row, 1, QTableWidgetItem(user.full_name))
            self._table.setItem(row, 2, QTableWidgetItem(user.role_name))
            self._table.setItem(
                row, 3, QTableWidgetItem("Activo" if user.is_active else "Inactivo")
            )
            self._table.setItem(row, 4, QTableWidgetItem(user.email or ""))

    def _on_new_user_clicked(self) -> None:
        if not self._roles:
            self._show_error("No hay roles disponibles. Crea un rol antes de crear un usuario.")
            return
        dialog = UserFormDialog(self._roles, self)
        if dialog.exec() == UserFormDialog.DialogCode.Accepted:
            self._view_model.create_user(**dialog.values())  # type: ignore[arg-type]

    def _on_toggle_active_clicked(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            self._show_error("Selecciona un usuario de la tabla.")
            return
        user = self._users[selected_rows[0].row()]
        self._view_model.set_active(user, not user.is_active)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
