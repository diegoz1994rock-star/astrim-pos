"""Diálogo de creación/edición de una báscula electrónica (Administración →
Dispositivos → Báscula electrónica).

Bluetooth/Ethernet/Wi-Fi aparecen en el combo de conexión pero deshabilitados
(nunca ocultos) — todavía no existe un driver real para ellos (solo
USB/Serial vía el adaptador genérico, y ningún puerto/socket para el
Simulador) — mismo principio de "nunca mostrar una opción como si
funcionara" que ya usa `HidWedgeDriver` en barcode_scanners."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from pos.modules.scales.application.dto import ScaleDeviceConfigDTO
from pos.modules.scales.application.providers.registry import SCALE_KIND_LABELS, SIMULATOR_KIND
from pos.modules.scales.domain.enums import ConnectionType, UnitOfMeasure

_DEFAULT_BAUD_RATE = "9600"
_CONNECTION_TYPE_LABELS: dict[ConnectionType, str] = {
    ConnectionType.USB: "USB",
    ConnectionType.SERIAL: "Puerto serial (COM)",
    ConnectionType.BLUETOOTH: "Bluetooth (no implementado)",
    ConnectionType.ETHERNET: "Ethernet / TCP-IP (no implementado)",
    ConnectionType.WIFI: "Wi-Fi (no implementado)",
}
_UNIMPLEMENTED_CONNECTION_TYPES = (
    ConnectionType.BLUETOOTH, ConnectionType.ETHERNET, ConnectionType.WIFI,
)
_UNIT_LABELS: dict[UnitOfMeasure, str] = {
    UnitOfMeasure.KG: "Kilogramos",
    UnitOfMeasure.G: "Gramos",
    UnitOfMeasure.LB: "Libras",
    UnitOfMeasure.OZ: "Onzas",
}
_PARITY_OPTIONS = [("Ninguna", "NONE"), ("Par", "EVEN"), ("Impar", "ODD")]


class ScaleDeviceFormDialog(QDialog):
    def __init__(
        self,
        existing_device: ScaleDeviceConfigDTO | None = None,
        cash_registers: list[tuple[int, str]] | None = None,
        users: list[tuple[int, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar báscula" if existing_device else "Nueva báscula")
        self.setMinimumWidth(420)
        self._cash_registers = cash_registers or []
        self._users = users or []
        self._values: dict[str, object] | None = None
        self._build_ui(existing_device)

    def _build_ui(self, existing_device: ScaleDeviceConfigDTO | None) -> None:
        form = self._form = QFormLayout(self)

        self._name_edit = QLineEdit(self)
        self._kind_combo = QComboBox(self)
        for kind, label in SCALE_KIND_LABELS.items():
            self._kind_combo.addItem(label, userData=kind)
        self._kind_combo.currentIndexChanged.connect(self._update_connection_fields)
        form.addRow("Nombre del dispositivo", self._name_edit)
        form.addRow("Adaptador", self._kind_combo)

        self._brand_edit = QLineEdit(self)
        self._model_edit = QLineEdit(self)
        self._serial_edit = QLineEdit(self)
        self._description_edit = QTextEdit(self)
        self._description_edit.setMaximumHeight(60)
        self._location_edit = QLineEdit(self)
        form.addRow("Marca", self._brand_edit)
        form.addRow("Modelo", self._model_edit)
        form.addRow("Número de serie", self._serial_edit)
        form.addRow("Descripción", self._description_edit)
        form.addRow("Ubicación", self._location_edit)

        self._cash_register_combo = QComboBox(self)
        self._cash_register_combo.addItem("(sin asignar)", userData=None)
        for register_id, name in self._cash_registers:
            self._cash_register_combo.addItem(name, userData=register_id)
        self._station_edit = QLineEdit(self)
        self._station_edit.setPlaceholderText("Ej. Caja 1 - PC Mostrador")
        self._user_combo = QComboBox(self)
        self._user_combo.addItem("(sin asignar)", userData=None)
        for user_id, name in self._users:
            self._user_combo.addItem(name, userData=user_id)
        form.addRow("Caja", self._cash_register_combo)
        form.addRow("Estación de trabajo", self._station_edit)
        form.addRow("Vendedor / usuario", self._user_combo)

        self._connection_type_combo = QComboBox(self)
        for connection_type, label in _CONNECTION_TYPE_LABELS.items():
            self._connection_type_combo.addItem(label, userData=connection_type)
        self._connection_type_combo.currentIndexChanged.connect(self._update_connection_fields)
        self._disable_unimplemented_connection_types()
        form.addRow("Tipo de conexión", self._connection_type_combo)

        self._port_edit = QLineEdit(self)
        self._port_edit.setPlaceholderText("Ej. COM3, /dev/ttyUSB0")
        self._baud_rate_edit = QLineEdit(self)
        self._baud_rate_edit.setText(_DEFAULT_BAUD_RATE)
        self._data_bits_edit = QLineEdit(self)
        self._data_bits_edit.setPlaceholderText("Ej. 8")
        self._stop_bits_edit = QLineEdit(self)
        self._stop_bits_edit.setPlaceholderText("Ej. 1")
        self._parity_combo = QComboBox(self)
        for label, value in _PARITY_OPTIONS:
            self._parity_combo.addItem(label, userData=value)
        form.addRow("Puerto COM", self._port_edit)
        form.addRow("Baud rate", self._baud_rate_edit)
        form.addRow("Bits de datos", self._data_bits_edit)
        form.addRow("Bits de parada", self._stop_bits_edit)
        form.addRow("Paridad", self._parity_combo)

        self._ip_address_edit = QLineEdit(self)
        self._ip_address_edit.setPlaceholderText("Ej. 192.168.1.50")
        self._ip_port_edit = QLineEdit(self)
        self._ip_port_edit.setPlaceholderText("Ej. 9100")
        form.addRow("Dirección IP", self._ip_address_edit)
        form.addRow("Puerto TCP", self._ip_port_edit)

        self._bluetooth_edit = QLineEdit(self)
        self._bluetooth_edit.setPlaceholderText("Dirección/MAC del dispositivo emparejado")
        form.addRow("Bluetooth", self._bluetooth_edit)

        self._unit_combo = QComboBox(self)
        for unit, label in _UNIT_LABELS.items():
            self._unit_combo.addItem(label, userData=unit)
        self._decimal_places_spin = QSpinBox(self)
        self._decimal_places_spin.setRange(0, 4)
        self._decimal_places_spin.setValue(3)
        self._timeout_spin = QSpinBox(self)
        self._timeout_spin.setRange(1, 30)
        self._timeout_spin.setValue(2)
        self._read_frequency_spin = QSpinBox(self)
        self._read_frequency_spin.setRange(1, 60)
        self._read_frequency_spin.setValue(1)
        self._auto_read_check = QCheckBox("Lectura automática (en vez de manual)")
        self._stability_required_check = QCheckBox("Peso estable requerido")
        self._stability_required_check.setChecked(True)
        self._min_stable_seconds_spin = QDoubleSpinBox(self)
        self._min_stable_seconds_spin.setRange(0.1, 10.0)
        self._min_stable_seconds_spin.setSingleStep(0.1)
        self._min_stable_seconds_spin.setValue(0.5)
        self._auto_reconnect_check = QCheckBox("Reconexión automática")
        self._auto_reconnect_check.setChecked(True)
        form.addRow("Unidad de medida", self._unit_combo)
        form.addRow("Decimales", self._decimal_places_spin)
        form.addRow("Tiempo de espera (s)", self._timeout_spin)
        form.addRow("Frecuencia de lectura (s)", self._read_frequency_spin)
        form.addRow(self._auto_read_check)
        form.addRow(self._stability_required_check)
        form.addRow("Tiempo mínimo estable (s)", self._min_stable_seconds_spin)
        form.addRow(self._auto_reconnect_check)

        self._simulator_target_edit = QLineEdit(self)
        self._simulator_target_edit.setPlaceholderText("Ej. 1.250 (opcional)")
        form.addRow("Peso simulado inicial", self._simulator_target_edit)

        if existing_device is not None:
            self._load_existing(existing_device)
        self._update_connection_fields()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _load_existing(self, device: ScaleDeviceConfigDTO) -> None:
        self._name_edit.setText(device.name)
        kind_index = self._kind_combo.findData(device.kind)
        if kind_index >= 0:
            self._kind_combo.setCurrentIndex(kind_index)
        self._brand_edit.setText(device.brand or "")
        self._model_edit.setText(device.model or "")
        self._serial_edit.setText(device.serial_number or "")
        self._description_edit.setPlainText(device.description or "")
        self._location_edit.setText(device.location or "")
        register_index = self._cash_register_combo.findData(device.cash_register_id)
        if register_index >= 0:
            self._cash_register_combo.setCurrentIndex(register_index)
        self._station_edit.setText(device.station_label or "")
        user_index = self._user_combo.findData(device.assigned_user_id)
        if user_index >= 0:
            self._user_combo.setCurrentIndex(user_index)
        connection_index = self._connection_type_combo.findData(device.connection_type)
        if connection_index >= 0:
            self._connection_type_combo.setCurrentIndex(connection_index)
        self._port_edit.setText(device.port or "")
        self._baud_rate_edit.setText(str(device.baud_rate) if device.baud_rate else "")
        self._data_bits_edit.setText(str(device.data_bits) if device.data_bits else "")
        self._stop_bits_edit.setText(str(device.stop_bits) if device.stop_bits else "")
        if device.parity:
            parity_index = self._parity_combo.findData(device.parity)
            if parity_index >= 0:
                self._parity_combo.setCurrentIndex(parity_index)
        self._ip_address_edit.setText(device.ip_address or "")
        self._ip_port_edit.setText(str(device.ip_port) if device.ip_port else "")
        self._bluetooth_edit.setText(device.bluetooth_address or "")
        unit_index = self._unit_combo.findData(device.unit_of_measure)
        if unit_index >= 0:
            self._unit_combo.setCurrentIndex(unit_index)
        self._decimal_places_spin.setValue(device.decimal_places)
        self._timeout_spin.setValue(device.timeout_seconds)
        self._read_frequency_spin.setValue(device.read_frequency_seconds)
        self._auto_read_check.setChecked(device.auto_read)
        self._stability_required_check.setChecked(device.stability_required)
        self._min_stable_seconds_spin.setValue(float(device.min_stable_seconds))
        self._auto_reconnect_check.setChecked(device.auto_reconnect)
        if device.simulator_target_weight is not None:
            self._simulator_target_edit.setText(str(device.simulator_target_weight))

    def _current_connection_type(self) -> ConnectionType:
        return self._connection_type_combo.currentData()

    def _current_kind(self) -> str:
        return self._kind_combo.currentData()

    def _disable_unimplemented_connection_types(self) -> None:
        """Bluetooth/Ethernet/Wi-Fi quedan visibles en el combo (para que
        quede claro que existen como opción futura) pero deshabilitados —
        nunca se pueden seleccionar como si funcionaran de verdad."""
        model = self._connection_type_combo.model()
        assert isinstance(model, QStandardItemModel)
        for row in range(self._connection_type_combo.count()):
            connection_type = self._connection_type_combo.itemData(row)
            if connection_type in _UNIMPLEMENTED_CONNECTION_TYPES:
                item = model.item(row)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _update_connection_fields(self) -> None:
        is_simulator = self._current_kind() == SIMULATOR_KIND
        connection_type = self._current_connection_type()
        is_serial = not is_simulator and connection_type in (
            ConnectionType.USB, ConnectionType.SERIAL,
        )
        is_ip = not is_simulator and connection_type in (
            ConnectionType.ETHERNET, ConnectionType.WIFI,
        )
        is_bluetooth = not is_simulator and connection_type is ConnectionType.BLUETOOTH
        self._set_row_visible(self._connection_type_combo, not is_simulator)
        for widget in (
            self._port_edit, self._baud_rate_edit, self._data_bits_edit,
            self._stop_bits_edit, self._parity_combo,
        ):
            self._set_row_visible(widget, is_serial)
        self._set_row_visible(self._ip_address_edit, is_ip)
        self._set_row_visible(self._ip_port_edit, is_ip)
        self._set_row_visible(self._bluetooth_edit, is_bluetooth)
        self._set_row_visible(self._simulator_target_edit, is_simulator)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre de la báscula es obligatorio.")
            return
        kind = self._current_kind()
        is_simulator = kind == SIMULATOR_KIND
        connection_type = self._current_connection_type()
        port = self._port_edit.text().strip() or None
        if (
            not is_simulator
            and connection_type in (ConnectionType.USB, ConnectionType.SERIAL)
            and not port
        ):
            QMessageBox.warning(self, "Error", "El puerto es obligatorio para USB/Serial.")
            return
        ip_address = self._ip_address_edit.text().strip() or None
        ip_port_text = self._ip_port_edit.text().strip()
        needs_ip = not is_simulator and connection_type in (
            ConnectionType.ETHERNET, ConnectionType.WIFI,
        )
        if needs_ip and (not ip_address or not ip_port_text):
            QMessageBox.warning(
                self, "Error", "La dirección IP y el puerto son obligatorios para Ethernet/Wi-Fi."
            )
            return
        try:
            baud_text = self._baud_rate_edit.text().strip()
            data_bits_text = self._data_bits_edit.text().strip()
            stop_bits_text = self._stop_bits_edit.text().strip()
            baud_rate = int(baud_text) if baud_text else None
            data_bits = int(data_bits_text) if data_bits_text else None
            stop_bits = float(stop_bits_text) if stop_bits_text else None
            ip_port = int(ip_port_text) if ip_port_text else None
        except ValueError:
            QMessageBox.warning(self, "Error", "Los campos numéricos deben ser números válidos.")
            return
        simulator_target_text = self._simulator_target_edit.text().strip()
        try:
            simulator_target_weight = (
                Decimal(simulator_target_text) if simulator_target_text else None
            )
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "El peso simulado debe ser un número válido.")
            return

        self._values = {
            "name": name,
            "kind": kind,
            "brand": self._brand_edit.text().strip() or None,
            "model": self._model_edit.text().strip() or None,
            "serial_number": self._serial_edit.text().strip() or None,
            "description": self._description_edit.toPlainText().strip() or None,
            "location": self._location_edit.text().strip() or None,
            "cash_register_id": self._cash_register_combo.currentData(),
            "station_label": self._station_edit.text().strip() or None,
            "assigned_user_id": self._user_combo.currentData(),
            "connection_type": connection_type,
            "port": port,
            "baud_rate": baud_rate,
            "data_bits": data_bits,
            "stop_bits": stop_bits,
            "parity": self._parity_combo.currentData(),
            "ip_address": ip_address,
            "ip_port": ip_port,
            "bluetooth_address": self._bluetooth_edit.text().strip() or None,
            "unit_of_measure": self._unit_combo.currentData(),
            "decimal_places": self._decimal_places_spin.value(),
            "timeout_seconds": self._timeout_spin.value(),
            "read_frequency_seconds": self._read_frequency_spin.value(),
            "auto_read": self._auto_read_check.isChecked(),
            "stability_required": self._stability_required_check.isChecked(),
            "min_stable_seconds": Decimal(str(self._min_stable_seconds_spin.value())),
            "auto_reconnect": self._auto_reconnect_check.isChecked(),
            "simulator_target_weight": simulator_target_weight,
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
