"""Pantalla de administración de números de Nequi (Administración → Pagos electrónicos)."""

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

from pos.modules.nequi_payments.application.dto import NequiPaymentConfigDTO
from pos.modules.nequi_payments.presentation.nequi_payment_config_form_dialog import (
    NequiPaymentConfigFormDialog,
)
from pos.modules.nequi_payments.presentation.nequi_payment_config_view_model import (
    NequiPaymentConfigViewModel,
)
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Número", "Predeterminado", "Estado"]


class NequiPaymentConfigView(QWidget):
    def __init__(
        self, view_model: NequiPaymentConfigViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._configs: list[NequiPaymentConfigDTO] = []
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
        toolbar.addWidget(make_section_title("Nequi"))
        toolbar.addStretch()
        self._add_button = QPushButton("Añadir número")
        toolbar.addWidget(self._add_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._on_table_double_clicked)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._change_button = QPushButton("Cambiar número")
        self._toggle_button = QPushButton("Activar/Desactivar seleccionado")
        self._set_default_button = QPushButton("Marcar como predeterminado")
        self._delete_button = QPushButton("Eliminar número")
        actions.addWidget(self._change_button)
        actions.addWidget(self._toggle_button)
        actions.addWidget(self._set_default_button)
        actions.addWidget(self._delete_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._add_button.clicked.connect(self._on_add_clicked)
        self._change_button.clicked.connect(self._on_change_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._set_default_button.clicked.connect(self._on_set_default_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._view_model.configs_loaded.connect(self._on_configs_loaded)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_configs_loaded(self, configs: list[NequiPaymentConfigDTO]) -> None:
        self._configs = configs
        self._table.setRowCount(len(configs))
        for row, config in enumerate(configs):
            self._table.setItem(row, 0, QTableWidgetItem(config.number))
            self._table.setItem(row, 1, QTableWidgetItem("Sí" if config.is_default else ""))
            status_text = "Activo" if config.is_active else "Inactivo"
            status_role = "success" if config.is_active else "secondary"
            self._table.setCellWidget(row, 2, StatusBadge(status_text, status_role))
        fit_table_to_contents(self._table)

    def _on_add_clicked(self) -> None:
        dialog = NequiPaymentConfigFormDialog(parent=self)
        if dialog.exec() != NequiPaymentConfigFormDialog.DialogCode.Accepted:
            return
        self._view_model.create_config(dialog.values()["number"])

    def _selected_config(self) -> NequiPaymentConfigDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._configs[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._configs[row])

    def _on_change_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un número de Nequi de la tabla.")
            return
        self._open_edit_dialog(config)

    def _open_edit_dialog(self, config: NequiPaymentConfigDTO) -> None:
        dialog = NequiPaymentConfigFormDialog(existing_config=config, parent=self)
        if dialog.exec() != NequiPaymentConfigFormDialog.DialogCode.Accepted:
            return
        self._view_model.update_config(config.id, dialog.values()["number"])

    def _on_toggle_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un número de Nequi de la tabla.")
            return
        self._view_model.set_active(config.id, not config.is_active)

    def _on_set_default_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un número de Nequi de la tabla.")
            return
        self._view_model.set_default(config.id)

    def _on_delete_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un número de Nequi de la tabla.")
            return
        confirm = QMessageBox.question(
            self, "Eliminar número", f"¿Eliminar el número de Nequi '{config.number}'?"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._view_model.delete_config(config.id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
