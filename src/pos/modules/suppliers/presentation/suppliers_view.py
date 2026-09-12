"""Pantalla de administración de proveedores."""

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

from pos.modules.suppliers.application.dto import SupplierDTO
from pos.modules.suppliers.presentation.supplier_form_dialog import SupplierFormDialog
from pos.modules.suppliers.presentation.suppliers_view_model import SuppliersViewModel
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_COLUMNS = ["Razón social", "Contacto", "Documento", "Teléfono"]


class SuppliersView(QWidget):
    def __init__(self, view_model: SuppliersViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._suppliers: list[SupplierDTO] = []
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
        title = make_section_title("Proveedores")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nuevo proveedor")
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        self._remove_button = QPushButton("Eliminar seleccionado")
        layout.addWidget(self._remove_button)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._remove_button.clicked.connect(self._on_remove_clicked)
        self._view_model.suppliers_loaded.connect(self._on_suppliers_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_suppliers_loaded(self, suppliers: list[SupplierDTO]) -> None:
        self._suppliers = suppliers
        self._table.setRowCount(len(suppliers))
        for row, supplier in enumerate(suppliers):
            self._table.setItem(row, 0, QTableWidgetItem(supplier.company_name))
            self._table.setItem(row, 1, QTableWidgetItem(supplier.contact_name or ""))
            self._table.setItem(row, 2, QTableWidgetItem(supplier.document_id or ""))
            self._table.setItem(row, 3, QTableWidgetItem(supplier.phone or ""))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = SupplierFormDialog(self)
        if dialog.exec() == SupplierFormDialog.DialogCode.Accepted:
            self._view_model.create_supplier(**dialog.values())

    def _on_remove_clicked(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            self._show_error("Selecciona un proveedor de la tabla.")
            return
        supplier = self._suppliers[selected_rows[0].row()]
        self._view_model.remove_supplier(supplier.id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
