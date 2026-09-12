"""Pantalla de administración de cajas registradoras (puntos de cobro)."""

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

from pos.modules.cash_register.application.dto import CashRegisterDTO
from pos.modules.cash_register.presentation.cash_register_form_dialog import (
    CashRegisterFormDialog,
)
from pos.modules.cash_register.presentation.cash_registers_view_model import (
    CashRegistersViewModel,
)
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Nombre", "Estado"]


class CashRegistersView(QWidget):
    def __init__(self, view_model: CashRegistersViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._registers: list[CashRegisterDTO] = []
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
        title = make_section_title("Cajas")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nueva caja")
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
        self._delete_button = QPushButton("Eliminar caja")
        self._toggle_button = QPushButton("Activar/Desactivar seleccionada")
        actions.addWidget(self._edit_button)
        actions.addWidget(self._delete_button)
        actions.addWidget(self._toggle_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._view_model.registers_loaded.connect(self._on_registers_loaded)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_registers_loaded(self, registers: list[CashRegisterDTO]) -> None:
        self._registers = registers
        self._table.setRowCount(len(registers))
        for row, register in enumerate(registers):
            self._table.setItem(row, 0, QTableWidgetItem(register.name))
            status_text = "Activa" if register.is_active else "Inactiva"
            status_role = "success" if register.is_active else "secondary"
            self._table.setCellWidget(row, 1, StatusBadge(status_text, status_role))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = CashRegisterFormDialog(parent=self)
        if dialog.exec() != CashRegisterFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.create_register(values["name"], values["location"])

    def _selected_register(self) -> CashRegisterDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._registers[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._registers[row])

    def _on_edit_clicked(self) -> None:
        register = self._selected_register()
        if register is None:
            self._show_error("Selecciona una caja de la tabla.")
            return
        self._open_edit_dialog(register)

    def _open_edit_dialog(self, register: CashRegisterDTO) -> None:
        dialog = CashRegisterFormDialog(existing_register=register, parent=self)
        if dialog.exec() != CashRegisterFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.update_register(register.id, values["name"], values["location"])

    def _on_delete_clicked(self) -> None:
        register = self._selected_register()
        if register is None:
            self._show_error("Selecciona una caja de la tabla.")
            return
        confirmed = QMessageBox.question(
            self,
            "Eliminar caja",
            f"¿Seguro que deseas eliminar la caja '{register.name}'? "
            "Esta acción no se puede deshacer.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._view_model.delete_register(register.id)

    def _on_toggle_clicked(self) -> None:
        register = self._selected_register()
        if register is None:
            self._show_error("Selecciona una caja de la tabla.")
            return
        self._view_model.set_active(register.id, not register.is_active)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
