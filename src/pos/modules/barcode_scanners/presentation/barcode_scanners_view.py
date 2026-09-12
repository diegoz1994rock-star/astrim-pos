"""Pantalla de administración de código de barras (Administración →
Dispositivos → Código de barras). Arriba: la configuración global y las
herramientas de Probar lector/Diagnóstico/Historial — funcionan de
inmediato con cualquier lector HID conectado, sin necesitar ningún
dispositivo registrado. Abajo, intacto: el inventario opcional de
dispositivos (útil para lectores seriales reales o para llevar un
registro físico), con su propio Probar/Diagnóstico/Historial
por-dispositivo — dos herramientas con el mismo nombre pero alcance
distinto, no lógica repetida (ambas terminan en el mismo
`BarcodeReadService`/`BarcodeScannerService` de siempre)."""

from __future__ import annotations

import serial.tools.list_ports
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.barcode_scanners.application.dto import BarcodeScannerDTO, BarcodeSettingsDTO
from pos.modules.barcode_scanners.application.providers.registry import CONNECTION_TYPE_LABELS
from pos.modules.barcode_scanners.domain.enums import ConnectionStatus
from pos.modules.barcode_scanners.presentation.barcode_diagnostics_dialog import (
    BarcodeDiagnosticsDialog,
)
from pos.modules.barcode_scanners.presentation.barcode_read_log_dialog import BarcodeReadLogDialog
from pos.modules.barcode_scanners.presentation.barcode_scanner_diagnostics_dialog import (
    BarcodeScannerDiagnosticsDialog,
)
from pos.modules.barcode_scanners.presentation.barcode_scanner_history_dialog import (
    BarcodeScannerHistoryDialog,
)
from pos.modules.barcode_scanners.presentation.barcode_scanner_test_panel_dialog import (
    BarcodeScannerTestPanelDialog,
)
from pos.modules.barcode_scanners.presentation.barcode_scanner_wizard_dialog import (
    BarcodeScannerWizardDialog,
)
from pos.modules.barcode_scanners.presentation.barcode_scanners_view_model import (
    BarcodeScannersViewModel,
)
from pos.modules.barcode_scanners.presentation.barcode_test_dialog import BarcodeTestDialog
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_DEBOUNCE_MIN_MS = 0
_DEBOUNCE_MAX_MS = 5000

_COLUMNS = [
    "Nombre", "Marca", "Modelo", "Tipo de conexión", "Puerto", "Estado", "Predeterminado",
    "Caja asignada", "Última lectura", "Última conexión", "Firmware", "Número de serie", "Batería",
]
_STATUS_ROLE = {
    ConnectionStatus.CONNECTED: ("Conectado", "success"),
    ConnectionStatus.DISCONNECTED: ("Desconectado", "secondary"),
    ConnectionStatus.ERROR: ("Error", "danger"),
}
_AUTO_DETECT_INTERVAL_MS = 4000


def _format_datetime(value: object) -> str:
    if value is None:
        return "—"
    return f"{value:%Y-%m-%d %H:%M:%S}"


class BarcodeScannersView(QWidget):
    def __init__(self, view_model: BarcodeScannersViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._devices: list[BarcodeScannerDTO] = []
        self._visible_devices: list[BarcodeScannerDTO] = []
        self._cash_register_names: dict[int, str] = {}
        self._cash_registers: list[tuple[int, str]] = []
        self._known_ports: set[str] = self._current_serial_ports()
        self._dismissed_ports: set[str] = set()
        self._build_ui()
        self._connect_signals()
        self._view_model.load()
        self._auto_detect_timer = QTimer(self)
        self._auto_detect_timer.setInterval(_AUTO_DETECT_INTERVAL_MS)
        self._auto_detect_timer.timeout.connect(self._check_for_new_devices)
        self._auto_detect_timer.start()

    def reload(self) -> None:
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)

        layout.addWidget(make_section_title("Código de barras"))
        layout.addLayout(self._build_settings_section())

        tools_row = QHBoxLayout()
        self._global_test_button = QPushButton("Probar lector")
        self._global_diagnostics_button = QPushButton("Diagnóstico")
        self._global_history_button = QPushButton("Ver historial")
        tools_row.addWidget(self._global_test_button)
        tools_row.addWidget(self._global_diagnostics_button)
        tools_row.addWidget(self._global_history_button)
        layout.addLayout(tools_row)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        toolbar = QHBoxLayout()
        toolbar.addWidget(
            make_section_title(
                "Dispositivos registrados (opcional — inventario o lectores seriales)"
            )
        )
        toolbar.addStretch()
        self._new_button = QPushButton("Agregar lector")
        self._search_devices_button = QPushButton("Buscar dispositivos")
        toolbar.addWidget(self._search_devices_button)
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
        self._delete_button = QPushButton("Eliminar")
        self._activate_button = QPushButton("Activar")
        self._deactivate_button = QPushButton("Desactivar")
        self._default_button = QPushButton("Marcar como predeterminado")
        for button in (
            self._edit_button, self._delete_button, self._activate_button,
            self._deactivate_button, self._default_button,
        ):
            management_row.addWidget(button)
        layout.addLayout(management_row)

        connection_row = QHBoxLayout()
        self._connect_button = QPushButton("Conectar")
        self._disconnect_button = QPushButton("Desconectar")
        self._test_button = QPushButton("Probar lector seleccionado")
        self._history_button = QPushButton("Historial del lector seleccionado")
        self._diagnostics_button = QPushButton("Diagnóstico del lector seleccionado")
        for button in (
            self._connect_button, self._disconnect_button, self._test_button,
            self._history_button, self._diagnostics_button,
        ):
            connection_row.addWidget(button)
        layout.addLayout(connection_row)

    def _build_settings_section(self) -> QHBoxLayout:
        self._reader_enabled_check = QCheckBox("Activar lector", self)
        self._auto_enter_check = QCheckBox("Aceptar Enter automático", self)
        self._sound_on_success_check = QCheckBox("Sonido al leer correctamente", self)
        self._sound_on_not_found_check = QCheckBox("Sonido cuando no encuentra producto", self)
        self._show_notification_check = QCheckBox("Mostrar notificación visual", self)

        left_column = QVBoxLayout()
        for checkbox in (
            self._reader_enabled_check,
            self._auto_enter_check,
            self._sound_on_success_check,
            self._sound_on_not_found_check,
            self._show_notification_check,
        ):
            left_column.addWidget(checkbox)

        right_column = QVBoxLayout()
        debounce_row = QHBoxLayout()
        debounce_row.addWidget(QLabel("Tiempo para ignorar duplicados:", self))
        self._debounce_spin = QSpinBox(self)
        self._debounce_spin.setRange(_DEBOUNCE_MIN_MS, _DEBOUNCE_MAX_MS)
        self._debounce_spin.setSuffix(" ms")
        debounce_row.addWidget(self._debounce_spin)
        right_column.addLayout(debounce_row)
        self._save_settings_button = QPushButton("Guardar configuración", self)
        right_column.addWidget(self._save_settings_button)
        right_column.addStretch()

        row = QHBoxLayout()
        row.addLayout(left_column)
        row.addLayout(right_column)
        return row

    def _connect_signals(self) -> None:
        self._global_test_button.clicked.connect(self._on_global_test_clicked)
        self._global_diagnostics_button.clicked.connect(self._on_global_diagnostics_clicked)
        self._global_history_button.clicked.connect(self._on_global_history_clicked)
        self._save_settings_button.clicked.connect(self._on_save_settings_clicked)
        self._view_model.barcode_settings_loaded.connect(self._on_barcode_settings_loaded)
        self._new_button.clicked.connect(self._on_new_clicked)
        self._search_devices_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._activate_button.clicked.connect(lambda: self._on_set_active(True))
        self._deactivate_button.clicked.connect(lambda: self._on_set_active(False))
        self._default_button.clicked.connect(self._on_default_clicked)
        self._connect_button.clicked.connect(self._on_connect_clicked)
        self._disconnect_button.clicked.connect(self._on_disconnect_clicked)
        self._test_button.clicked.connect(self._on_test_clicked)
        self._history_button.clicked.connect(self._on_history_clicked)
        self._diagnostics_button.clicked.connect(self._on_diagnostics_clicked)
        self._search_edit.textChanged.connect(self._render_table)
        self._view_model.devices_loaded.connect(self._on_devices_loaded)
        self._view_model.cash_registers_loaded.connect(self._on_cash_registers_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)
        self._view_model.busy_changed.connect(self._on_busy_changed)

    def _on_barcode_settings_loaded(self, settings: BarcodeSettingsDTO) -> None:
        self._reader_enabled_check.setChecked(settings.reader_enabled)
        self._auto_enter_check.setChecked(settings.auto_enter_enabled)
        self._debounce_spin.setValue(settings.duplicate_debounce_ms)
        self._sound_on_success_check.setChecked(settings.sound_on_success)
        self._sound_on_not_found_check.setChecked(settings.sound_on_not_found)
        self._show_notification_check.setChecked(settings.show_visual_notification)

    def _on_save_settings_clicked(self) -> None:
        self._view_model.save_barcode_settings(
            BarcodeSettingsDTO(
                reader_enabled=self._reader_enabled_check.isChecked(),
                auto_enter_enabled=self._auto_enter_check.isChecked(),
                duplicate_debounce_ms=self._debounce_spin.value(),
                sound_on_success=self._sound_on_success_check.isChecked(),
                sound_on_not_found=self._sound_on_not_found_check.isChecked(),
                show_visual_notification=self._show_notification_check.isChecked(),
            )
        )

    def _on_global_test_clicked(self) -> None:
        dialog = BarcodeTestDialog(self._view_model.barcode_read_service, parent=self)
        dialog.exec()

    def _on_global_diagnostics_clicked(self) -> None:
        dialog = BarcodeDiagnosticsDialog(self._view_model.barcode_read_service, parent=self)
        dialog.exec()

    def _on_global_history_clicked(self) -> None:
        dialog = BarcodeReadLogDialog(self._view_model.barcode_read_service, parent=self)
        dialog.exec()

    def _on_busy_changed(self, busy: bool) -> None:
        for button in (
            self._connect_button, self._disconnect_button, self._test_button,
        ):
            button.setEnabled(not busy)

    def _on_cash_registers_loaded(self, registers: list[tuple[int, str]]) -> None:
        self._cash_registers = registers
        self._cash_register_names = dict(registers)
        self._render_table()

    def _on_devices_loaded(self, devices: list[BarcodeScannerDTO]) -> None:
        self._devices = devices
        self._render_table()

    def _render_table(self) -> None:
        query = self._search_edit.text().strip().lower()
        self._visible_devices = [
            d
            for d in self._devices
            if not query
            or query in " ".join(filter(None, [d.name, d.brand, d.model, d.serial_number])).lower()
        ]
        self._table.setRowCount(len(self._visible_devices))
        for row, device in enumerate(self._visible_devices):
            register_name = self._cash_register_names.get(device.cash_register_id or -1, "—")
            battery = (
                f"{device.battery_level_percent}%"
                if device.battery_level_percent is not None
                else "—"
            )
            self._table.setItem(row, 0, QTableWidgetItem(device.name))
            self._table.setItem(row, 1, QTableWidgetItem(device.brand or "—"))
            self._table.setItem(row, 2, QTableWidgetItem(device.model or "—"))
            self._table.setItem(
                row, 3, QTableWidgetItem(CONNECTION_TYPE_LABELS[device.connection_type])
            )
            self._table.setItem(row, 4, QTableWidgetItem(device.port or device.ip_address or "—"))
            text, role = _STATUS_ROLE[device.connection_status]
            self._table.setCellWidget(row, 5, StatusBadge(text, role))
            self._table.setItem(row, 6, QTableWidgetItem("Sí" if device.is_default else "No"))
            self._table.setItem(row, 7, QTableWidgetItem(register_name))
            self._table.setItem(row, 8, QTableWidgetItem(_format_datetime(device.last_read_at)))
            self._table.setItem(
                row, 9, QTableWidgetItem(_format_datetime(device.last_successful_communication_at))
            )
            self._table.setItem(row, 10, QTableWidgetItem(device.firmware_version or "—"))
            self._table.setItem(row, 11, QTableWidgetItem(device.serial_number or "—"))
            self._table.setItem(row, 12, QTableWidgetItem(battery))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = BarcodeScannerWizardDialog(cash_registers=self._cash_registers, parent=self)
        if dialog.exec() != BarcodeScannerWizardDialog.DialogCode.Accepted:
            return
        self._view_model.create_device(**dialog.values())

    def _selected_device(self) -> BarcodeScannerDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._visible_devices[selected_rows[0].row()]

    def _on_table_double_clicked(self, row: int, _column: int) -> None:
        self._open_edit_dialog(self._visible_devices[row])

    def _on_edit_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        self._open_edit_dialog(device)

    def _open_edit_dialog(self, device: BarcodeScannerDTO) -> None:
        dialog = BarcodeScannerWizardDialog(
            existing_device=device, cash_registers=self._cash_registers, parent=self
        )
        if dialog.exec() != BarcodeScannerWizardDialog.DialogCode.Accepted:
            return
        self._view_model.update_device(device.id, **dialog.values())

    def _on_delete_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        confirmed = QMessageBox.question(
            self,
            "Eliminar lector",
            f"¿Seguro que deseas eliminar '{device.name}'? Esta acción no se puede deshacer.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._view_model.delete_device(device.id)

    def _on_set_active(self, is_active: bool) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        self._view_model.set_active(device.id, is_active)

    def _on_default_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        self._view_model.set_default(device.id)

    def _on_connect_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        self._view_model.connect_device(device.id)

    def _on_disconnect_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        self._view_model.disconnect_device(device.id)

    def _on_test_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        dialog = BarcodeScannerTestPanelDialog(
            self._view_model.service, device.id, device.name, device.connection_type, parent=self
        )
        dialog.exec()
        self._view_model.load()

    def _on_history_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        history = self._view_model.service.list_scan_history(device.id)
        dialog = BarcodeScannerHistoryDialog(
            history, self._cash_register_names, device.name, parent=self
        )
        dialog.exec()

    def _on_diagnostics_clicked(self) -> None:
        device = self._selected_device()
        if device is None:
            self._show_error("Selecciona un lector de la tabla.")
            return
        dialog = BarcodeScannerDiagnosticsDialog(self._view_model.service, device, parent=self)
        dialog.exec()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)

    # -- detección automática de dispositivos ----------------------------
    # Solo cubre los 3 modos serie (USB-Serial/Bluetooth-Serial/RS232): son
    # los únicos detectables de forma confiable sin una librería nativa
    # adicional (pyusb/hidapi, no instalada) — límite honesto, documentado
    # en el plan de este módulo, no simulado.

    def _current_serial_ports(self) -> set[str]:
        return {port_info.device for port_info in serial.tools.list_ports.comports()}

    def _registered_ports(self) -> set[str]:
        return {device.port for device in self._devices if device.port}

    def _check_for_new_devices(self) -> None:
        current_ports = self._current_serial_ports()
        known = self._known_ports | self._registered_ports() | self._dismissed_ports
        new_ports = current_ports - known
        self._known_ports |= current_ports
        for port in sorted(new_ports):
            self._prompt_register_new_port(port)

    def _prompt_register_new_port(self, port: str) -> None:
        confirmed = QMessageBox.question(
            self,
            "Lector detectado",
            f"Se detectó un nuevo dispositivo en el puerto '{port}'. ¿Desea registrarlo?",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            self._dismissed_ports.add(port)
            return
        dialog = BarcodeScannerWizardDialog(cash_registers=self._cash_registers, parent=self)
        dialog.preselect_serial_port(port)
        if dialog.exec() != BarcodeScannerWizardDialog.DialogCode.Accepted:
            self._dismissed_ports.add(port)
            return
        self._view_model.create_device(**dialog.values())
