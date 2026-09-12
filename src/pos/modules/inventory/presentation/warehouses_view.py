"""Pantalla de administración de bodegas."""

from __future__ import annotations

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

from pos.modules.inventory.application.dto import StockLevelDTO, WarehouseDTO
from pos.modules.inventory.presentation.warehouse_form_dialog import WarehouseFormDialog
from pos.modules.inventory.presentation.warehouse_products_dialog import WarehouseProductsDialog
from pos.modules.inventory.presentation.warehouses_view_model import WarehousesViewModel
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Nombre", "Ubicación", "Estado"]


class WarehousesView(QWidget):
    def __init__(self, view_model: WarehousesViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._warehouses: list[WarehouseDTO] = []
        self._pending_warehouse_name = ""
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
        title = make_section_title("Bodegas")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nueva bodega")
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._on_table_double_clicked)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._edit_button = QPushButton("Editar")
        self._toggle_button = QPushButton("Activar/Desactivar seleccionada")
        self._view_products_button = QPushButton("Ver productos")
        actions.addWidget(self._edit_button)
        actions.addWidget(self._toggle_button)
        actions.addWidget(self._view_products_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._view_products_button.clicked.connect(self._on_view_products_clicked)
        self._view_model.warehouses_loaded.connect(self._on_warehouses_loaded)
        self._view_model.warehouse_products_loaded.connect(self._on_warehouse_products_loaded)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_warehouses_loaded(self, warehouses: list[WarehouseDTO]) -> None:
        self._warehouses = warehouses
        self._table.setRowCount(len(warehouses))
        for row, warehouse in enumerate(warehouses):
            self._table.setItem(row, 0, QTableWidgetItem(warehouse.name))
            self._table.setItem(row, 1, QTableWidgetItem(warehouse.location or ""))
            status_text = "Activa" if warehouse.is_active else "Inactiva"
            status_role = "success" if warehouse.is_active else "secondary"
            self._table.setCellWidget(row, 2, StatusBadge(status_text, status_role))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = WarehouseFormDialog(parent=self)
        if dialog.exec() != WarehouseFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.create_warehouse(values["name"], values["location"])

    def _selected_warehouse(self) -> WarehouseDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._warehouses[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._warehouses[row])

    def _on_edit_clicked(self) -> None:
        warehouse = self._selected_warehouse()
        if warehouse is None:
            self._show_error("Selecciona una bodega de la tabla.")
            return
        self._open_edit_dialog(warehouse)

    def _open_edit_dialog(self, warehouse: WarehouseDTO) -> None:
        dialog = WarehouseFormDialog(existing_warehouse=warehouse, parent=self)
        if dialog.exec() != WarehouseFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.update_warehouse(warehouse.id, values["name"], values["location"])

    def _on_toggle_clicked(self) -> None:
        warehouse = self._selected_warehouse()
        if warehouse is None:
            self._show_error("Selecciona una bodega de la tabla.")
            return
        self._view_model.set_active(warehouse.id, not warehouse.is_active)

    def _on_view_products_clicked(self) -> None:
        warehouse = self._selected_warehouse()
        if warehouse is None:
            self._show_error("Selecciona una bodega de la tabla.")
            return
        self._pending_warehouse_name = warehouse.name
        self._view_model.load_warehouse_products(warehouse.id)

    def _on_warehouse_products_loaded(self, products: list[StockLevelDTO]) -> None:
        dialog = WarehouseProductsDialog(self._pending_warehouse_name, products, parent=self)
        dialog.exec()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
