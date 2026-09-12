"""Pantalla de administración de códigos QR estáticos (Administración → Pagos electrónicos)."""

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

from pos.modules.qr_payments.application.dto import QrPaymentConfigDTO
from pos.modules.qr_payments.presentation.qr_payment_config_form_dialog import (
    QrPaymentConfigFormDialog,
)
from pos.modules.qr_payments.presentation.qr_payment_config_view_model import (
    QrPaymentConfigViewModel,
)
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Nombre", "Predeterminado", "Estado"]


class QrPaymentConfigView(QWidget):
    def __init__(self, view_model: QrPaymentConfigViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._configs: list[QrPaymentConfigDTO] = []
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
        toolbar.addWidget(make_section_title("QR"))
        toolbar.addStretch()
        self._new_button = QPushButton("Nuevo QR")
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
        self._toggle_button = QPushButton("Activar/Desactivar seleccionado")
        self._set_default_button = QPushButton("Marcar como predeterminado")
        self._delete_button = QPushButton("Eliminar")
        actions.addWidget(self._edit_button)
        actions.addWidget(self._toggle_button)
        actions.addWidget(self._set_default_button)
        actions.addWidget(self._delete_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._set_default_button.clicked.connect(self._on_set_default_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._view_model.configs_loaded.connect(self._on_configs_loaded)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_configs_loaded(self, configs: list[QrPaymentConfigDTO]) -> None:
        self._configs = configs
        self._table.setRowCount(len(configs))
        for row, config in enumerate(configs):
            self._table.setItem(row, 0, QTableWidgetItem(config.name))
            self._table.setItem(row, 1, QTableWidgetItem("Sí" if config.is_default else ""))
            status_text = "Activo" if config.is_active else "Inactivo"
            status_role = "success" if config.is_active else "secondary"
            self._table.setCellWidget(row, 2, StatusBadge(status_text, status_role))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = QrPaymentConfigFormDialog(parent=self)
        if dialog.exec() != QrPaymentConfigFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.create_config(values["name"], values["image_path"])

    def _selected_config(self) -> QrPaymentConfigDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._configs[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._configs[row])

    def _on_edit_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un QR de la tabla.")
            return
        self._open_edit_dialog(config)

    def _open_edit_dialog(self, config: QrPaymentConfigDTO) -> None:
        dialog = QrPaymentConfigFormDialog(existing_config=config, parent=self)
        if dialog.exec() != QrPaymentConfigFormDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.update_config(config.id, values["name"], values["image_path"])

    def _on_toggle_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un QR de la tabla.")
            return
        self._view_model.set_active(config.id, not config.is_active)

    def _on_set_default_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un QR de la tabla.")
            return
        self._view_model.set_default(config.id)

    def _on_delete_clicked(self) -> None:
        config = self._selected_config()
        if config is None:
            self._show_error("Selecciona un QR de la tabla.")
            return
        confirm = QMessageBox.question(
            self, "Eliminar QR", f"¿Eliminar el QR '{config.name}'?"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._view_model.delete_config(config.id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
