"""Pantalla de administración de básculas electrónicas (Administración →
Dispositivos → Báscula electrónica): múltiples básculas, cada una con su
tipo de conexión, estado en vivo, pruebas e historial."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.scales.application.dto import ScaleDeviceConfigDTO
from pos.modules.scales.application.providers.registry import SCALE_KIND_LABELS
from pos.modules.scales.domain.enums import ConnectionStatus
from pos.modules.scales.presentation.scale_device_form_dialog import ScaleDeviceFormDialog
from pos.modules.scales.presentation.scale_device_history_dialog import ScaleDeviceHistoryDialog
from pos.modules.scales.presentation.scale_diagnostics_dialog import ScaleDiagnosticsDialog
from pos.modules.scales.presentation.scale_read_log_dialog import ScaleReadLogDialog
from pos.modules.scales.presentation.scale_test_panel_dialog import ScaleTestPanelDialog
from pos.modules.scales.presentation.scales_view_model import ScalesViewModel
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_COLUMNS = ["Nombre", "Marca / Modelo", "Conexión", "Caja", "Predeterminada", "Activa", "Estado"]
_STATUS_ROLE = {
    ConnectionStatus.CONNECTED: ("Conectada", "success"),
    ConnectionStatus.DISCONNECTED: ("Desconectada", "secondary"),
    ConnectionStatus.ERROR: ("Error de comunicación", "danger"),
}


def _connection_summary(device: ScaleDeviceConfigDTO) -> str:
    if device.port:
        return device.port
    if device.ip_address:
        return f"{device.ip_address}:{device.ip_port}" if device.ip_port else device.ip_address
    if device.bluetooth_address:
        return device.bluetooth_address
    return "—"


class ScalesView(QWidget):
    def __init__(self, view_model: ScalesViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._devices: list[ScaleDeviceConfigDTO] = []
        self._visible_devices: list[ScaleDeviceConfigDTO] = []
        self._cash_register_names: dict[int, str] = {}
        self._cash_registers: list[tuple[int, str]] = []
        self._users: list[tuple[int, str]] = []
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
        toolbar.addWidget(make_section_title("Báscula electrónica"))
        toolbar.addStretch()
        self._global_diagnostics_button = QPushButton("Diagnóstico")
        self._global_history_button = QPushButton("Historial de lecturas")
        self._new_button = QPushButton("Agregar báscula")
        toolbar.addWidget(self._global_diagnostics_button)
        toolbar.addWidget(self._global_history_button)
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Buscar por nombre, marca, modelo o número de serie…")
        layout.addWidget(self._search_edit)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._on_table_double_clicked)
        layout.addWidget(self._table)

        management_row = QHBoxLayout()
        self._edit_button = QPushButton("Editar")
        self._delete_button = QPushButton("Eliminar báscula")
        self._toggle_button = QPushButton("Activar/Desactivar")
        self._set_default_button = QPushButton("Marcar como predeterminada")
        for button in (
            self._edit_button, self._delete_button, self._toggle_button, self._set_default_button,
        ):
            management_row.addWidget(button)
        layout.addLayout(management_row)

        connection_row = QHBoxLayout()
        self._connect_button = QPushButton("Conectar")
        self._disconnect_button = QPushButton("Desconectar")
        self._test_connection_button = QPushButton("Probar conexión")
        self._tests_button = QPushButton("Pruebas")
        self._history_button = QPushButton("Historial y diagnóstico")
        for button in (
            self._connect_button, self._disconnect_button, self._test_connection_button,
            self._tests_button, self._history_button,
        ):
            connection_row.addWidget(button)
        layout.addLayout(connection_row)

    def _connect_signals(self) -> None:
        self._global_diagnostics_button.clicked.connect(self._on_global_diagnostics_clicked)
        self._global_history_button.clicked.connect(self._on_global_history_clicked)
        self._new_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._set_default_button.clicked.connect(self._on_set_default_clicked)
        self._connect_button.clicked.connect(self._on_connect_clicked)
        self._disconnect_button.clicked.connect(self._on_disconnect_clicked)
        self._test_connection_button.clicked.connect(self._on_test_connection_clicked)
        self._tests_button.clicked.connect(self._on_tests_clicked)
        self._history_button.clicked.connect(self._on_history_clicked)
        self._search_edit.textChanged.connect(self._render_table)
        self._view_model.devices_loaded.connect(self._on_devices_loaded)
        self._view_model.cash_registers_loaded.connect(self._on_cash_registers_loaded)
        self._view_model.users_loaded.connect(self._on_users_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)
        self._view_model.busy_changed.connect(self._on_busy_changed)

    def _on_busy_changed(self, busy: bool) -> None:
        for button in (self._connect_button, self._test_connection_button):
            button.setEnabled(not busy)

    def _on_cash_registers_loaded(self, registers: list[tuple[int, str]]) -> None:
        self._cash_registers = registers
        self._cash_register_names = dict(registers)
        self._render_table()

    def _on_users_loaded(self, users: list[tuple[int, str]]) -> None:
        self._users = users

    def _on_devices_loaded(self, devices: list[ScaleDeviceConfigDTO]) -> None:
        self._devices = devices
        self._render_table()

    def _render_table(self) -> None:
        query = self._search_edit.text().strip().lower()
        self._visible_devices = [
            d
            for d in self._devices
            if not query
            or query
            in " ".join(filter(None, [d.name, d.brand, d.model, d.serial_number])).lower()
        ]
        self._table.setRowCount(len(self._visible_devices))
        for row, device in enumerate(self._visible_devices):
            kind_label = SCALE_KIND_LABELS.get(device.kind, device.kind)
            brand_model = " / ".join(filter(None, [device.brand, device.model])) or kind_label
            register_name = self._cash_register_names.get(device.cash_register_id or -1, "—")
            self._table.setItem(row, 0, QTableWidgetItem(device.name))
            self._table.setItem(row, 1, QTableWidgetItem(brand_model))
            self._table.setItem(row, 2, QTableWidgetItem(_connection_summary(device)))
            self._table.setItem(row, 3, QTableWidgetItem(register_name))
            self._table.setItem(row, 4, QTableWidgetItem("Sí" if device.is_default else ""))
            self._table.setItem(
                row, 5, QTableWidgetItem("Activa" if device.is_active else "Inactiva")
            )
            text, role = _STATUS_ROLE[device.connection_status]
            self._table.setCellWidget(row, 6, StatusBadge(text, role))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = ScaleDeviceFormDialog(
            cash_registers=self._cash_registers, users=self._users, parent=self
        )
        if dialog.exec() != ScaleDeviceFormDialog.DialogCode.Accepted:
            return
        self._view_model.create_device(**dialog.values())

    def _selected_device(self) -> ScaleDeviceConfigDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._visible_devices[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._visible_devices[row])

    def _on_edit_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        self._open_edit_dialog(device)

    def _open_edit_dialog(self, device: ScaleDeviceConfigDTO) -> None:
        dialog = ScaleDeviceFormDialog(
            existing_device=device,
            cash_registers=self._cash_registers,
            users=self._users,
            parent=self,
        )
        if dialog.exec() != ScaleDeviceFormDialog.DialogCode.Accepted:
            return
        self._view_model.update_device(device.id, **dialog.values())

    def _on_delete_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        confirmed = QMessageBox.question(
            self,
            "Eliminar báscula",
            f"¿Seguro que deseas eliminar la báscula '{device.name}'? "
            "Esta acción no se puede deshacer.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._view_model.delete_device(device.id)

    def _on_toggle_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        self._view_model.set_active(device.id, not device.is_active)

    def _on_set_default_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        self._view_model.set_default(device.id)

    def _on_connect_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        self._view_model.connect_device(device.id)

    def _on_disconnect_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        self._view_model.disconnect_device(device.id)

    def _on_test_connection_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        self._view_model.test_connection(device.id)

    def _on_tests_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        dialog = ScaleTestPanelDialog(
            self._view_model.service,
            self._view_model.scale_read_service,
            device.id,
            device.name,
            parent=self,
        )
        dialog.exec()

    def _on_global_diagnostics_clicked(self) -> None:
        dialog = ScaleDiagnosticsDialog(self._view_model.scale_read_service, parent=self)
        dialog.exec()

    def _on_global_history_clicked(self) -> None:
        dialog = ScaleReadLogDialog(self._view_model.scale_read_service, parent=self)
        dialog.exec()

    def _on_history_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona una báscula de la tabla.")
            return
        events = self._view_model.service.list_events(device.id)
        dialog = ScaleDeviceHistoryDialog(events, device.name, parent=self)
        dialog.exec()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
