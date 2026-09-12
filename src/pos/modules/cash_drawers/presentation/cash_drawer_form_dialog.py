"""Diálogo de creación/edición de un cajón monedero (Administración →
Dispositivos → Cajón monedero)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.modules.cash_drawers.application.dto import CashDrawerDTO
from pos.modules.cash_drawers.domain.enums import ConnectionType, OpeningType
from pos.modules.cash_drawers.domain.escpos_command import build_kick_command

_DEFAULT_BAUD_RATE = "9600"
_OPENING_TYPE_LABELS: dict[OpeningType, str] = {
    OpeningType.PRINTER_KICKOUT: "Kick-out por impresora (RJ11)",
    OpeningType.DIRECT_USB: "Directo por USB",
    OpeningType.DIRECT_SERIAL: "Directo por puerto serie",
    OpeningType.DIRECT_ETHERNET: "Directo por Ethernet",
}
_CONNECTION_TYPE_LABELS: dict[ConnectionType, str] = {
    ConnectionType.USB: "USB",
    ConnectionType.SERIAL: "Puerto serial (COM)",
    ConnectionType.BLUETOOTH: "Bluetooth",
    ConnectionType.ETHERNET: "Ethernet (TCP/IP)",
    ConnectionType.WIFI: "Wi-Fi",
}


class CashDrawerFormDialog(QDialog):
    def __init__(
        self,
        existing_device: CashDrawerDTO | None = None,
        cash_registers: list[tuple[int, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar cajón" if existing_device else "Nuevo cajón")
        self.setMinimumWidth(420)
        self._cash_registers = cash_registers or []
        self._values: dict[str, object] | None = None
        self._build_ui(existing_device)

    def _build_ui(self, existing_device: CashDrawerDTO | None) -> None:
        form = self._form = QFormLayout(self)

        self._name_edit = QLineEdit(self)
        self._brand_edit = QLineEdit(self)
        self._model_edit = QLineEdit(self)
        self._serial_edit = QLineEdit(self)
        self._location_edit = QLineEdit(self)
        form.addRow("Nombre", self._name_edit)
        form.addRow("Marca", self._brand_edit)
        form.addRow("Modelo", self._model_edit)
        form.addRow("Número de serie", self._serial_edit)
        form.addRow("Ubicación", self._location_edit)

        self._cash_register_combo = QComboBox(self)
        self._cash_register_combo.addItem("(sin asignar)", userData=None)
        for register_id, name in self._cash_registers:
            self._cash_register_combo.addItem(name, userData=register_id)
        form.addRow("Caja", self._cash_register_combo)

        self._opening_type_combo = QComboBox(self)
        for opening_type, label in _OPENING_TYPE_LABELS.items():
            self._opening_type_combo.addItem(label, userData=opening_type)
        form.addRow("Tipo de apertura", self._opening_type_combo)

        self._linked_printer_edit = QLineEdit(self)
        self._linked_printer_edit.setPlaceholderText("Nombre descriptivo de la impresora fiscal/térmica")
        form.addRow("Impresora asociada (descriptivo)", self._linked_printer_edit)

        self._connection_type_combo = QComboBox(self)
        for connection_type, label in _CONNECTION_TYPE_LABELS.items():
            self._connection_type_combo.addItem(label, userData=connection_type)
        self._connection_type_combo.currentIndexChanged.connect(self._update_opening_fields)
        form.addRow("Tipo de conexión", self._connection_type_combo)

        self._port_edit = QLineEdit(self)
        self._port_edit.setPlaceholderText("Ej. COM3, /dev/ttyUSB0")
        self._baud_rate_edit = QLineEdit(self)
        self._baud_rate_edit.setText(_DEFAULT_BAUD_RATE)
        form.addRow("Puerto COM", self._port_edit)
        form.addRow("Baud rate", self._baud_rate_edit)

        self._ip_address_edit = QLineEdit(self)
        self._ip_address_edit.setPlaceholderText("Ej. 192.168.1.70")
        self._ip_port_edit = QLineEdit(self)
        self._ip_port_edit.setPlaceholderText("Ej. 9100")
        form.addRow("Dirección IP", self._ip_address_edit)
        form.addRow("Puerto TCP", self._ip_port_edit)

        self._timeout_spin = QSpinBox(self)
        self._timeout_spin.setRange(1, 30)
        self._timeout_spin.setValue(2)
        form.addRow("Tiempo de espera (s)", self._timeout_spin)

        self._pulse_count_spin = QSpinBox(self)
        self._pulse_count_spin.setRange(1, 10)
        self._pulse_count_spin.setValue(1)
        form.addRow("Número de pulsos", self._pulse_count_spin)

        self._pulse_duration_spin = QSpinBox(self)
        self._pulse_duration_spin.setRange(0, 500)
        self._pulse_duration_spin.setValue(50)
        form.addRow("Duración del pulso (ms)", self._pulse_duration_spin)

        self._custom_command_edit = QLineEdit(self)
        self._custom_command_edit.setPlaceholderText(
            "Opcional — hex, ej. 1b70001964 (reemplaza el comando estándar)"
        )
        form.addRow("Comando personalizado", self._custom_command_edit)

        self._auto_open_check = QCheckBox("Apertura automática después de una venta")
        form.addRow(self._auto_open_check)

        if existing_device is not None:
            self._load_existing(existing_device)
        self._update_opening_fields()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _load_existing(self, device: CashDrawerDTO) -> None:
        self._name_edit.setText(device.name)
        self._brand_edit.setText(device.brand or "")
        self._model_edit.setText(device.model or "")
        self._serial_edit.setText(device.serial_number or "")
        self._location_edit.setText(device.location or "")
        register_index = self._cash_register_combo.findData(device.cash_register_id)
        if register_index >= 0:
            self._cash_register_combo.setCurrentIndex(register_index)
        opening_type_index = self._opening_type_combo.findData(device.opening_type)
        if opening_type_index >= 0:
            self._opening_type_combo.setCurrentIndex(opening_type_index)
        self._linked_printer_edit.setText(device.linked_printer_name or "")
        connection_index = self._connection_type_combo.findData(device.connection_type)
        if connection_index >= 0:
            self._connection_type_combo.setCurrentIndex(connection_index)
        self._port_edit.setText(device.port or "")
        self._baud_rate_edit.setText(str(device.baud_rate) if device.baud_rate else "")
        self._ip_address_edit.setText(device.ip_address or "")
        self._ip_port_edit.setText(str(device.ip_port) if device.ip_port else "")
        self._timeout_spin.setValue(device.timeout_seconds)
        self._pulse_count_spin.setValue(device.pulse_count)
        self._pulse_duration_spin.setValue(device.pulse_duration_ms)
        self._custom_command_edit.setText(device.custom_command_hex or "")
        self._auto_open_check.setChecked(device.auto_open_after_sale)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _update_opening_fields(self) -> None:
        connection_type = self._connection_type_combo.currentData()
        is_serial = connection_type in (ConnectionType.USB, ConnectionType.SERIAL)
        is_ip = connection_type in (ConnectionType.ETHERNET, ConnectionType.WIFI)
        for widget in (self._port_edit, self._baud_rate_edit):
            self._set_row_visible(widget, is_serial)
        self._set_row_visible(self._ip_address_edit, is_ip)
        self._set_row_visible(self._ip_port_edit, is_ip)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre del cajón es obligatorio.")
            return
        connection_type = self._connection_type_combo.currentData()
        port = self._port_edit.text().strip() or None
        ip_address = self._ip_address_edit.text().strip() or None
        ip_port_text = self._ip_port_edit.text().strip()
        if connection_type in (ConnectionType.USB, ConnectionType.SERIAL) and not port:
            QMessageBox.warning(self, "Error", "El puerto es obligatorio para USB/Serial.")
            return
        if connection_type in (ConnectionType.ETHERNET, ConnectionType.WIFI) and (
            not ip_address or not ip_port_text
        ):
            QMessageBox.warning(
                self, "Error",
                "La dirección IP y el puerto son obligatorios para Ethernet/Wi-Fi.",
            )
            return
        try:
            baud_text = self._baud_rate_edit.text().strip()
            baud_rate = int(baud_text) if baud_text else None
            ip_port = int(ip_port_text) if ip_port_text else None
        except ValueError:
            QMessageBox.warning(self, "Error", "Los campos numéricos deben ser números enteros.")
            return

        custom_command_hex = self._custom_command_edit.text().strip() or None
        try:
            build_kick_command(
                pulse_count=self._pulse_count_spin.value(),
                pulse_duration_ms=self._pulse_duration_spin.value(),
                custom_command_hex=custom_command_hex,
            )
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
            return

        self._values = {
            "name": name,
            "brand": self._brand_edit.text().strip() or None,
            "model": self._model_edit.text().strip() or None,
            "serial_number": self._serial_edit.text().strip() or None,
            "location": self._location_edit.text().strip() or None,
            "cash_register_id": self._cash_register_combo.currentData(),
            "opening_type": self._opening_type_combo.currentData(),
            "linked_printer_name": self._linked_printer_edit.text().strip() or None,
            "connection_type": connection_type,
            "port": port,
            "baud_rate": baud_rate,
            "ip_address": ip_address,
            "ip_port": ip_port,
            "timeout_seconds": self._timeout_spin.value(),
            "pulse_count": self._pulse_count_spin.value(),
            "pulse_duration_ms": self._pulse_duration_spin.value(),
            "custom_command_hex": custom_command_hex,
            "auto_open_after_sale": self._auto_open_check.isChecked(),
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
