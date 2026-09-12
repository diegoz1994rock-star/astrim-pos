"""Pantalla "Áreas y cargos": catálogo organizacional en árbol (área →
cargos), con creación, renombrado y eliminación de ambos niveles, más un
panel de permisos por cargo (qué módulos del menú principal ve ese
cargo)."""

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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.job_positions.application.dto import JobAreaDTO, JobPositionDTO
from pos.modules.job_positions.presentation.job_positions_view_model import (
    JobPositionsViewModel,
)
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_list_to_contents
from pos.shared_ui.widgets.toast import show_toast

_ROLE_KIND = Qt.ItemDataRole.UserRole
_ROLE_ID = Qt.ItemDataRole.UserRole + 1
_ROLE_CODE = Qt.ItemDataRole.UserRole
"""Rol de dato usado en `_permissions_list` (widget distinto del árbol,
así que no colisiona con `_ROLE_KIND` pese a compartir el mismo valor)."""
_KIND_AREA = "area"
_KIND_POSITION = "position"


class JobPositionsView(QWidget):
    """Vista de administración del catálogo de áreas y cargos."""

    def __init__(
        self, view_model: JobPositionsViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._areas: list[JobAreaDTO] = []
        self._selected_position_id: int | None = None
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, page_layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)

        layout = QHBoxLayout()
        page_layout.addLayout(layout)

        left_column = QVBoxLayout()
        title = make_section_title("Áreas y cargos")
        left_column.addWidget(title)

        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_column.addWidget(self._tree, stretch=1)

        buttons = QHBoxLayout()
        self._new_area_button = QPushButton("Nueva área")
        self._new_position_button = QPushButton("Nuevo cargo")
        self._rename_button = QPushButton("Renombrar")
        self._delete_button = QPushButton("Eliminar")
        buttons.addWidget(self._new_area_button)
        buttons.addWidget(self._new_position_button)
        buttons.addWidget(self._rename_button)
        buttons.addWidget(self._delete_button)
        left_column.addLayout(buttons)
        layout.addLayout(left_column, stretch=1)

        right_column = QVBoxLayout()
        permissions_title = QLabel("Permisos del cargo seleccionado")
        permissions_title_font = permissions_title.font()
        permissions_title_font.setBold(True)
        permissions_title_font.setPointSize(14)
        permissions_title.setFont(permissions_title_font)
        right_column.addWidget(permissions_title)

        self._permissions_hint = QLabel(
            "Selecciona un cargo en la lista para ver y editar sus permisos."
        )
        self._permissions_hint.setWordWrap(True)
        right_column.addWidget(self._permissions_hint)

        self._permissions_list = QListWidget(self)
        self._permissions_list.setEnabled(False)
        right_column.addWidget(self._permissions_list)

        self._save_permissions_button = QPushButton("Guardar permisos")
        self._save_permissions_button.setEnabled(False)
        right_column.addWidget(self._save_permissions_button)
        layout.addLayout(right_column, stretch=1)

    def _connect_signals(self) -> None:
        self._new_area_button.clicked.connect(self._on_new_area_clicked)
        self._new_position_button.clicked.connect(self._on_new_position_clicked)
        self._rename_button.clicked.connect(self._on_rename_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._save_permissions_button.clicked.connect(self._on_save_permissions_clicked)
        self._tree.currentItemChanged.connect(self._on_tree_selection_changed)
        self._view_model.areas_loaded.connect(self._on_areas_loaded)
        self._view_model.permission_catalog_loaded.connect(self._on_permission_catalog_loaded)
        self._view_model.permissions_loaded.connect(self._on_permissions_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_permission_catalog_loaded(self, catalog: list[tuple[str, str]]) -> None:
        self._permissions_list.clear()
        for code, label in catalog:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(_ROLE_CODE, code)
            self._permissions_list.addItem(item)
        fit_list_to_contents(self._permissions_list)

    def _on_areas_loaded(self, areas: list[JobAreaDTO]) -> None:
        self._areas = areas
        expanded_area_ids = self._expanded_area_ids()
        selected_kind, selected_id = self._selected_kind_and_id()

        self._tree.clear()
        for area in areas:
            area_item = QTreeWidgetItem([area.name])
            area_item.setData(0, _ROLE_KIND, _KIND_AREA)
            area_item.setData(0, _ROLE_ID, area.id)
            # Se parte de la fuente del propio árbol (`self._tree.font()`), no de
            # `area_item.font(0)`: un `QTreeWidgetItem` recién creado no hereda
            # la familia de fuente del stylesheet de la app, solo la del
            # widget contenedor una vez mostrado.
            area_font = self._tree.font()
            area_font.setBold(True)
            area_item.setFont(0, area_font)
            self._tree.addTopLevelItem(area_item)

            for position in area.positions:
                position_item = QTreeWidgetItem([position.name])
                position_item.setData(0, _ROLE_KIND, _KIND_POSITION)
                position_item.setData(0, _ROLE_ID, position.id)
                area_item.addChild(position_item)

            area_item.setExpanded(area.id in expanded_area_ids or not expanded_area_ids)

        if selected_kind is not None:
            self._select_item(selected_kind, selected_id)

    def _expanded_area_ids(self) -> set[int]:
        expanded = set()
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item.isExpanded():
                expanded.add(item.data(0, _ROLE_ID))
        return expanded

    def _selected_kind_and_id(self) -> tuple[str | None, int | None]:
        item = self._tree.currentItem()
        if item is None:
            return None, None
        return item.data(0, _ROLE_KIND), item.data(0, _ROLE_ID)

    def _select_item(self, kind: str, item_id: int | None) -> None:
        for index in range(self._tree.topLevelItemCount()):
            area_item = self._tree.topLevelItem(index)
            if kind == _KIND_AREA and area_item.data(0, _ROLE_ID) == item_id:
                self._tree.setCurrentItem(area_item)
                return
            if kind == _KIND_POSITION:
                for child_index in range(area_item.childCount()):
                    position_item = area_item.child(child_index)
                    if position_item.data(0, _ROLE_ID) == item_id:
                        self._tree.setCurrentItem(position_item)
                        return

    def _find_position(self, position_id: int) -> JobPositionDTO | None:
        for area in self._areas:
            for position in area.positions:
                if position.id == position_id:
                    return position
        return None

    def _on_tree_selection_changed(self) -> None:
        kind, item_id = self._selected_kind_and_id()
        if kind != _KIND_POSITION or item_id is None:
            self._selected_position_id = None
            self._permissions_list.setEnabled(False)
            self._save_permissions_button.setEnabled(False)
            self._permissions_hint.setText(
                "Selecciona un cargo en la lista para ver y editar sus permisos."
            )
            self._permissions_hint.setVisible(True)
            return

        position = self._find_position(item_id)
        if position is not None and position.grants_full_access:
            self._selected_position_id = None
            self._permissions_list.setEnabled(False)
            self._save_permissions_button.setEnabled(False)
            self._permissions_hint.setText(
                "'Administrador General' tiene acceso completo: no aplica "
                "restricción de permisos."
            )
            self._permissions_hint.setVisible(True)
            return

        self._selected_position_id = item_id
        self._permissions_list.setEnabled(True)
        self._save_permissions_button.setEnabled(True)
        self._permissions_hint.setVisible(False)
        self._view_model.load_permissions(item_id)

    def _on_permissions_loaded(self, position_id: int, codes: list[str]) -> None:
        if position_id != self._selected_position_id:
            return
        granted = set(codes)
        for index in range(self._permissions_list.count()):
            item = self._permissions_list.item(index)
            code = item.data(_ROLE_CODE)
            item.setCheckState(
                Qt.CheckState.Checked if code in granted else Qt.CheckState.Unchecked
            )

    def _on_save_permissions_clicked(self) -> None:
        if self._selected_position_id is None:
            return
        codes = [
            self._permissions_list.item(i).data(_ROLE_CODE)
            for i in range(self._permissions_list.count())
            if self._permissions_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        self._view_model.save_permissions(self._selected_position_id, codes)

    def _on_new_area_clicked(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nueva área", "Nombre del área:")
        if accepted and name.strip():
            self._view_model.create_area(name.strip())

    def _on_new_position_clicked(self) -> None:
        kind, item_id = self._selected_kind_and_id()
        area_id = item_id if kind == _KIND_AREA else None
        if area_id is None:
            self._show_error("Selecciona un área para agregarle un cargo.")
            return
        name, accepted = QInputDialog.getText(self, "Nuevo cargo", "Nombre del cargo:")
        if accepted and name.strip():
            self._view_model.create_position(area_id, name.strip())

    def _on_rename_clicked(self) -> None:
        kind, item_id = self._selected_kind_and_id()
        if kind is None:
            self._show_error("Selecciona un área o un cargo para renombrar.")
            return
        current_item = self._tree.currentItem()
        name, accepted = QInputDialog.getText(
            self, "Renombrar", "Nuevo nombre:", text=current_item.text(0)
        )
        if not accepted or not name.strip():
            return
        if kind == _KIND_AREA:
            self._view_model.rename_area(item_id, name.strip())
        else:
            self._view_model.rename_position(item_id, name.strip())

    def _on_delete_clicked(self) -> None:
        kind, item_id = self._selected_kind_and_id()
        if kind is None:
            self._show_error("Selecciona un área o un cargo para eliminar.")
            return
        current_item = self._tree.currentItem()
        if kind == _KIND_AREA:
            question = (
                f"Esto eliminará el área '{current_item.text(0)}' y todos sus cargos. "
                "¿Continuar?"
            )
        else:
            question = f"¿Eliminar el cargo '{current_item.text(0)}'?"
        confirmation = QMessageBox.question(self, "Confirmar eliminación", question)
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        if kind == _KIND_AREA:
            self._view_model.delete_area(item_id)
        else:
            self._view_model.delete_position(item_id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
