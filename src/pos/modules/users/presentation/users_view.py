"""Pantalla de administración de usuarios: tabla + alta + activar/desactivar/eliminar."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.job_positions.application.dto import JobAreaDTO
from pos.modules.users.application.dto import UserDTO
from pos.modules.users.presentation.user_form_dialog import UserFormDialog
from pos.modules.users.presentation.users_view_model import UsersViewModel
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_COLUMNS = ["Foto", "Usuario", "Nombre completo", "Área", "Cargo", "Estado", "Correo"]
_PHOTO_COLUMN = 0

# Miniatura retrato 3x4 (ancho:alto), fija y chica, acorde a la altura de fila.
_THUMB_WIDTH = 45
_THUMB_HEIGHT = 60
_ROW_HEIGHT = _THUMB_HEIGHT + 8


def _placeholder_photo() -> QPixmap:
    """Ícono genérico de "sin foto": silueta simple sobre fondo gris."""
    pixmap = QPixmap(_THUMB_WIDTH, _THUMB_HEIGHT)
    pixmap.fill(QColor("#E0E0E0"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#BDBDBD"))

    head_diameter = _THUMB_WIDTH * 0.42
    head_x = (_THUMB_WIDTH - head_diameter) / 2
    head_y = _THUMB_HEIGHT * 0.16
    painter.drawEllipse(QRectF(head_x, head_y, head_diameter, head_diameter))

    body_width = _THUMB_WIDTH * 0.72
    body_x = (_THUMB_WIDTH - body_width) / 2
    body_y = head_y + head_diameter * 0.85
    painter.drawRoundedRect(QRectF(body_x, body_y, body_width, _THUMB_HEIGHT - body_y), 4, 4)
    painter.end()
    return pixmap


def _photo_thumbnail(photo_path: str | None) -> QPixmap:
    """`QPixmap` no se puede construir antes de que exista una
    `QApplication` — por eso el placeholder se genera bajo demanda acá, no
    como constante de módulo (rompería el import en cualquier contexto
    donde este módulo se cargue antes de crear la `QApplication`, ej. en
    tests)."""
    if photo_path:
        pixmap = QPixmap(photo_path)
        if not pixmap.isNull():
            return pixmap.scaled(
                _THUMB_WIDTH,
                _THUMB_HEIGHT,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
    return _placeholder_photo()


class UsersView(QWidget):
    """Vista de administración de usuarios."""

    def __init__(self, view_model: UsersViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._areas: list[JobAreaDTO] = []
        self._users: list[UserDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)

        toolbar = QHBoxLayout()
        title = make_section_title("Usuarios")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._new_user_button = QPushButton("Nuevo usuario")
        toolbar.addWidget(self._new_user_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            _PHOTO_COLUMN, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(_PHOTO_COLUMN, _THUMB_WIDTH + 16)
        self._table.setIconSize(QSize(_THUMB_WIDTH, _THUMB_HEIGHT))
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._on_table_double_clicked)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._edit_user_button = QPushButton("Editar")
        self._toggle_active_button = QPushButton("Activar/Desactivar seleccionado")
        self._delete_user_button = QPushButton("Eliminar usuario")
        actions.addWidget(self._edit_user_button)
        actions.addWidget(self._toggle_active_button)
        actions.addWidget(self._delete_user_button)
        actions.addStretch()
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_user_button.clicked.connect(self._on_new_user_clicked)
        self._edit_user_button.clicked.connect(self._on_edit_user_clicked)
        self._toggle_active_button.clicked.connect(self._on_toggle_active_clicked)
        self._delete_user_button.clicked.connect(self._on_delete_user_clicked)
        self._view_model.users_loaded.connect(self._on_users_loaded)
        self._view_model.areas_loaded.connect(self._on_areas_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_areas_loaded(self, areas: list[JobAreaDTO]) -> None:
        self._areas = areas

    def _on_users_loaded(self, users: list[UserDTO]) -> None:
        self._users = users
        self._table.setRowCount(len(users))
        for row, user in enumerate(users):
            photo_item = QTableWidgetItem()
            photo_item.setIcon(QIcon(_photo_thumbnail(user.photo_path)))
            self._table.setItem(row, _PHOTO_COLUMN, photo_item)
            self._table.setItem(row, 1, QTableWidgetItem(user.username))
            self._table.setItem(row, 2, QTableWidgetItem(user.full_name))
            self._table.setItem(row, 3, QTableWidgetItem(user.job_area_name or ""))
            self._table.setItem(row, 4, QTableWidgetItem(user.job_position_name or ""))
            status_text = "Activo" if user.is_active else "Inactivo"
            status_role = "success" if user.is_active else "secondary"
            self._table.setCellWidget(row, 5, StatusBadge(status_text, status_role))
            self._table.setItem(row, 6, QTableWidgetItem(user.email or ""))
        fit_table_to_contents(self._table)

    def _on_new_user_clicked(self) -> None:
        # `UserFormDialog` llama a `create_user` internamente (en su propio
        # botón Aceptar) para poder mantenerse abierto y mostrar errores de
        # validación junto al campo correspondiente — acá no hay que
        # volver a crear el usuario, el `exec()` ya hizo todo el trabajo.
        dialog = UserFormDialog(self._areas, self._view_model, parent=self)
        dialog.exec()

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._users[row])

    def _on_edit_user_clicked(self) -> None:
        user = self._selected_user()
        if user is None:
            self._show_error("Selecciona un usuario de la tabla.")
            return
        self._open_edit_dialog(user)

    def _open_edit_dialog(self, user: UserDTO) -> None:
        dialog = UserFormDialog(self._areas, self._view_model, existing_user=user, parent=self)
        dialog.exec()

    def _selected_user(self) -> UserDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._users[selected_rows[0].row()]

    def _on_toggle_active_clicked(self) -> None:
        user = self._selected_user()
        if user is None:
            self._show_error("Selecciona un usuario de la tabla.")
            return
        self._view_model.set_active(user, not user.is_active)

    def _on_delete_user_clicked(self) -> None:
        user = self._selected_user()
        if user is None:
            self._show_error("Selecciona un usuario de la tabla.")
            return

        box = QMessageBox(self)
        box.setWindowTitle("Eliminar usuario")
        box.setText("¿Está seguro de eliminar este usuario?")
        yes_button = box.addButton("Sí", QMessageBox.ButtonRole.YesRole)
        box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == yes_button:
            self._view_model.delete_user(user)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
