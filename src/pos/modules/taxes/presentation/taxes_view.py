"""Pantalla de administración de impuestos (Administración → Impuestos)."""

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

from pos.modules.taxes.application.dto import TaxDTO
from pos.modules.taxes.presentation.tax_form_dialog import TaxFormDialog
from pos.modules.taxes.presentation.taxes_view_model import TaxesViewModel
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Nombre", "Porcentaje", "Estado"]


class TaxesView(QWidget):
    def __init__(self, view_model: TaxesViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._taxes: list[TaxDTO] = []
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
        title = make_section_title("Impuestos")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nuevo impuesto")
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
        self._delete_button = QPushButton("Eliminar impuesto")
        self._toggle_button = QPushButton("Activar/Desactivar seleccionado")
        actions.addWidget(self._edit_button)
        actions.addWidget(self._delete_button)
        actions.addWidget(self._toggle_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._view_model.taxes_loaded.connect(self._on_taxes_loaded)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_taxes_loaded(self, taxes: list[TaxDTO]) -> None:
        self._taxes = taxes
        self._table.setRowCount(len(taxes))
        for row, tax in enumerate(taxes):
            self._table.setItem(row, 0, QTableWidgetItem(tax.name))
            self._table.setItem(row, 1, QTableWidgetItem(f"{tax.rate_percent}%"))
            status_text = "Activo" if tax.is_active else "Inactivo"
            status_role = "success" if tax.is_active else "secondary"
            self._table.setCellWidget(row, 2, StatusBadge(status_text, status_role))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = TaxFormDialog(parent=self)
        if dialog.exec() != TaxFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.create_tax(values["name"], values["rate_percent"])

    def _selected_tax(self) -> TaxDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._taxes[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._taxes[row])

    def _on_edit_clicked(self) -> None:
        tax = self._selected_tax()
        if tax is None:
            self._show_error("Selecciona un impuesto de la tabla.")
            return
        self._open_edit_dialog(tax)

    def _open_edit_dialog(self, tax: TaxDTO) -> None:
        dialog = TaxFormDialog(existing_tax=tax, parent=self)
        if dialog.exec() != TaxFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.update_tax(tax.id, values["name"], values["rate_percent"])

    def _on_delete_clicked(self) -> None:
        tax = self._selected_tax()
        if tax is None:
            self._show_error("Selecciona un impuesto de la tabla.")
            return
        confirmed = QMessageBox.question(
            self,
            "Eliminar impuesto",
            f"¿Seguro que deseas eliminar el impuesto '{tax.name}'? "
            "Esta acción no se puede deshacer.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._view_model.delete_tax(tax.id)

    def _on_toggle_clicked(self) -> None:
        tax = self._selected_tax()
        if tax is None:
            self._show_error("Selecciona un impuesto de la tabla.")
            return
        self._view_model.set_active(tax.id, not tax.is_active)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
