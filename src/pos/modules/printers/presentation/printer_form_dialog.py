"""Diálogo de creación/edición de una impresora (Administración →
Dispositivos → Impresoras)."""

from __future__ import annotations

from decimal import Decimal

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
    QWidget,
)

from pos.modules.invoice_settings.presentation.printer_discovery import list_printer_names
from pos.modules.printers.application.dto import PrinterDTO
from pos.modules.printers.application.providers.registry import (
    PRINT_METHOD_LABELS,
    PRINTER_TYPE_LABELS,
)
from pos.modules.printers.domain.enums import ConnectionType, Orientation, PrintMethod

_CONNECTION_TYPE_LABELS: dict[ConnectionType, str] = {
    ConnectionType.USB: "USB",
    ConnectionType.SERIAL: "Puerto serial (COM)",
    ConnectionType.BLUETOOTH: "Bluetooth",
    ConnectionType.ETHERNET: "Ethernet (TCP/IP)",
    ConnectionType.WIFI: "Wi-Fi",
    ConnectionType.SHARED_NETWORK: "Compartida en red (SO)",
}
_ORIENTATION_LABELS: dict[Orientation, str] = {
    Orientation.PORTRAIT: "Vertical",
    Orientation.LANDSCAPE: "Horizontal",
}


class PrinterFormDialog(QDialog):
    def __init__(
        self,
        existing_device: PrinterDTO | None = None,
        cash_registers: list[tuple[int, str]] | None = None,
        detected_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar impresora" if existing_device else "Nueva impresora")
        self.setMinimumWidth(460)
        self._cash_registers = cash_registers or []
        self._values: dict[str, object] | None = None
        self._build_ui(existing_device, detected_name)

    def _build_ui(self, existing_device: PrinterDTO | None, detected_name: str | None) -> None:
        form = self._form = QFormLayout(self)

        self._name_edit = QLineEdit(self)
        self._alias_edit = QLineEdit(self)
        self._brand_edit = QLineEdit(self)
        self._model_edit = QLineEdit(self)
        self._serial_edit = QLineEdit(self)
        form.addRow("Nombre", self._name_edit)
        form.addRow("Alias", self._alias_edit)
        form.addRow("Marca", self._brand_edit)
        form.addRow("Modelo", self._model_edit)
        form.addRow("Número de serie", self._serial_edit)

        self._type_combo = QComboBox(self)
        for printer_type, label in PRINTER_TYPE_LABELS.items():
            self._type_combo.addItem(label, userData=printer_type)
        form.addRow("Tipo de impresora", self._type_combo)

        self._print_method_combo = QComboBox(self)
        for method, label in PRINT_METHOD_LABELS.items():
            self._print_method_combo.addItem(label, userData=method)
        self._print_method_combo.currentIndexChanged.connect(self._update_method_fields)
        form.addRow("Método de impresión", self._print_method_combo)

        self._system_printer_combo = QComboBox(self)
        self._system_printer_combo.setEditable(True)
        for name in list_printer_names():
            self._system_printer_combo.addItem(name)
        form.addRow("Impresora del sistema", self._system_printer_combo)

        self._connection_type_combo = QComboBox(self)
        for connection_type, label in _CONNECTION_TYPE_LABELS.items():
            self._connection_type_combo.addItem(label, userData=connection_type)
        self._connection_type_combo.currentIndexChanged.connect(self._update_method_fields)
        form.addRow("Tipo de conexión", self._connection_type_combo)

        self._port_edit = QLineEdit(self)
        self._port_edit.setPlaceholderText("Ej. COM3, /dev/ttyUSB0")
        self._baud_rate_spin = QSpinBox(self)
        self._baud_rate_spin.setRange(1200, 921600)
        self._baud_rate_spin.setValue(9600)
        form.addRow("Puerto", self._port_edit)
        form.addRow("Baud rate", self._baud_rate_spin)

        self._ip_address_edit = QLineEdit(self)
        self._ip_address_edit.setPlaceholderText("Ej. 192.168.1.80")
        self._ip_port_spin = QSpinBox(self)
        self._ip_port_spin.setRange(1, 65535)
        self._ip_port_spin.setValue(9100)
        form.addRow("Dirección IP", self._ip_address_edit)
        form.addRow("Puerto TCP", self._ip_port_spin)

        self._timeout_spin = QSpinBox(self)
        self._timeout_spin.setRange(1, 60)
        self._timeout_spin.setValue(5)
        form.addRow("Tiempo de espera (s)", self._timeout_spin)

        self._cash_register_combo = QComboBox(self)
        self._cash_register_combo.addItem("(sin asignar)", userData=None)
        for register_id, name in self._cash_registers:
            self._cash_register_combo.addItem(name, userData=register_id)
        form.addRow("Caja asignada", self._cash_register_combo)

        self._area_edit = QLineEdit(self)
        self._area_edit.setPlaceholderText("Ej. Caja 1, Cocina, Despacho, Administración")
        form.addRow("Área", self._area_edit)

        self._copies_spin = QSpinBox(self)
        self._copies_spin.setRange(1, 10)
        self._copies_spin.setValue(1)
        form.addRow("Copias", self._copies_spin)

        self._orientation_combo = QComboBox(self)
        for orientation, label in _ORIENTATION_LABELS.items():
            self._orientation_combo.addItem(label, userData=orientation)
        form.addRow("Orientación", self._orientation_combo)

        self._margin_top_spin = self._make_margin_spin()
        self._margin_right_spin = self._make_margin_spin()
        self._margin_bottom_spin = self._make_margin_spin()
        self._margin_left_spin = self._make_margin_spin()
        form.addRow("Margen superior (mm)", self._margin_top_spin)
        form.addRow("Margen derecho (mm)", self._margin_right_spin)
        form.addRow("Margen inferior (mm)", self._margin_bottom_spin)
        form.addRow("Margen izquierdo (mm)", self._margin_left_spin)

        self._resolution_spin = QSpinBox(self)
        self._resolution_spin.setRange(72, 1200)
        self._resolution_spin.setValue(203)
        form.addRow("Resolución (DPI)", self._resolution_spin)

        self._paper_width_spin = QDoubleSpinBox(self)
        self._paper_width_spin.setRange(10, 1000)
        self._paper_width_spin.setDecimals(2)
        self._paper_width_spin.setValue(80)
        form.addRow("Ancho de papel (mm)", self._paper_width_spin)

        self._paper_length_spin = QDoubleSpinBox(self)
        self._paper_length_spin.setRange(0, 2000)
        self._paper_length_spin.setDecimals(2)
        self._paper_length_spin.setSpecialValueText("Rollo continuo")
        form.addRow("Largo de papel (mm)", self._paper_length_spin)

        self._auto_cut_check = QCheckBox("Corte automático")
        self._auto_cut_check.setChecked(True)
        form.addRow(self._auto_cut_check)

        self._open_drawer_check = QCheckBox("Abrir cajón monedero después de imprimir")
        form.addRow(self._open_drawer_check)

        self._show_dialog_check = QCheckBox("Mostrar diálogo de impresión del sistema")
        form.addRow(self._show_dialog_check)

        if existing_device is not None:
            self._load_existing(existing_device)
        elif detected_name is not None:
            self._name_edit.setText(detected_name)
            self._system_printer_combo.setCurrentText(detected_name)
        self._update_method_fields()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _make_margin_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(0, 100)
        spin.setDecimals(2)
        spin.setValue(5)
        return spin

    def _load_existing(self, device: PrinterDTO) -> None:
        self._name_edit.setText(device.name)
        self._alias_edit.setText(device.alias or "")
        self._brand_edit.setText(device.brand or "")
        self._model_edit.setText(device.model or "")
        self._serial_edit.setText(device.serial_number or "")
        type_index = self._type_combo.findData(device.printer_type)
        if type_index >= 0:
            self._type_combo.setCurrentIndex(type_index)
        method_index = self._print_method_combo.findData(device.print_method)
        if method_index >= 0:
            self._print_method_combo.setCurrentIndex(method_index)
        if device.system_printer_name:
            self._system_printer_combo.setCurrentText(device.system_printer_name)
        connection_index = self._connection_type_combo.findData(device.connection_type)
        if connection_index >= 0:
            self._connection_type_combo.setCurrentIndex(connection_index)
        self._port_edit.setText(device.port or "")
        if device.baud_rate:
            self._baud_rate_spin.setValue(device.baud_rate)
        self._ip_address_edit.setText(device.ip_address or "")
        if device.ip_port:
            self._ip_port_spin.setValue(device.ip_port)
        self._timeout_spin.setValue(device.timeout_seconds)
        register_index = self._cash_register_combo.findData(device.cash_register_id)
        if register_index >= 0:
            self._cash_register_combo.setCurrentIndex(register_index)
        self._area_edit.setText(device.area or "")
        self._copies_spin.setValue(device.copies)
        orientation_index = self._orientation_combo.findData(device.orientation)
        if orientation_index >= 0:
            self._orientation_combo.setCurrentIndex(orientation_index)
        self._margin_top_spin.setValue(float(device.margin_top_mm))
        self._margin_right_spin.setValue(float(device.margin_right_mm))
        self._margin_bottom_spin.setValue(float(device.margin_bottom_mm))
        self._margin_left_spin.setValue(float(device.margin_left_mm))
        self._resolution_spin.setValue(device.resolution_dpi)
        self._paper_width_spin.setValue(float(device.paper_width_mm))
        self._paper_length_spin.setValue(
            float(device.paper_length_mm) if device.paper_length_mm is not None else 0
        )
        self._auto_cut_check.setChecked(device.auto_cut)
        self._open_drawer_check.setChecked(device.open_drawer_after_print)
        self._show_dialog_check.setChecked(device.show_dialog)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _update_method_fields(self) -> None:
        print_method = self._print_method_combo.currentData()
        is_system_driver = print_method is PrintMethod.SYSTEM_DRIVER
        self._set_row_visible(self._system_printer_combo, is_system_driver)

        connection_type = self._connection_type_combo.currentData()
        is_serial = connection_type in (
            ConnectionType.USB, ConnectionType.SERIAL, ConnectionType.BLUETOOTH,
        )
        is_ip = connection_type in (ConnectionType.ETHERNET, ConnectionType.WIFI)
        self._set_row_visible(self._connection_type_combo, not is_system_driver)
        for widget in (self._port_edit, self._baud_rate_spin):
            self._set_row_visible(widget, not is_system_driver and is_serial)
        for widget in (self._ip_address_edit, self._ip_port_spin):
            self._set_row_visible(widget, not is_system_driver and is_ip)
        self._set_row_visible(self._show_dialog_check, is_system_driver)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre de la impresora es obligatorio.")
            return

        print_method = self._print_method_combo.currentData()
        connection_type = self._connection_type_combo.currentData()
        system_printer_name = self._system_printer_combo.currentText().strip() or None
        port = self._port_edit.text().strip() or None
        ip_address = self._ip_address_edit.text().strip() or None

        if print_method is PrintMethod.SYSTEM_DRIVER and not system_printer_name:
            QMessageBox.warning(
                self, "Error", "Selecciona la impresora del sistema operativo."
            )
            return
        if print_method is PrintMethod.RAW_ESCPOS:
            if connection_type in (
                ConnectionType.USB, ConnectionType.SERIAL, ConnectionType.BLUETOOTH,
            ) and not port:
                QMessageBox.warning(
                    self, "Error", "El puerto es obligatorio para USB/Serial/Bluetooth."
                )
                return
            if connection_type in (ConnectionType.ETHERNET, ConnectionType.WIFI) and not ip_address:
                QMessageBox.warning(
                    self, "Error", "La dirección IP es obligatoria para Ethernet/Wi-Fi."
                )
                return

        paper_length = self._paper_length_spin.value()
        self._values = {
            "name": name,
            "alias": self._alias_edit.text().strip() or None,
            "brand": self._brand_edit.text().strip() or None,
            "model": self._model_edit.text().strip() or None,
            "serial_number": self._serial_edit.text().strip() or None,
            "printer_type": self._type_combo.currentData(),
            "print_method": print_method,
            "system_printer_name": system_printer_name,
            "connection_type": connection_type,
            "port": port,
            "baud_rate": self._baud_rate_spin.value(),
            "ip_address": ip_address,
            "ip_port": self._ip_port_spin.value(),
            "timeout_seconds": self._timeout_spin.value(),
            "cash_register_id": self._cash_register_combo.currentData(),
            "area": self._area_edit.text().strip() or None,
            "copies": self._copies_spin.value(),
            "orientation": self._orientation_combo.currentData(),
            "margin_top_mm": Decimal(str(self._margin_top_spin.value())),
            "margin_right_mm": Decimal(str(self._margin_right_spin.value())),
            "margin_bottom_mm": Decimal(str(self._margin_bottom_spin.value())),
            "margin_left_mm": Decimal(str(self._margin_left_spin.value())),
            "resolution_dpi": self._resolution_spin.value(),
            "paper_width_mm": Decimal(str(self._paper_width_spin.value())),
            "paper_length_mm": Decimal(str(paper_length)) if paper_length > 0 else None,
            "auto_cut": self._auto_cut_check.isChecked(),
            "open_drawer_after_print": self._open_drawer_check.isChecked(),
            "show_dialog": self._show_dialog_check.isChecked(),
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
