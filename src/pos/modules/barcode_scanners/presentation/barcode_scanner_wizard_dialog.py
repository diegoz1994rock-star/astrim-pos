"""Asistente de registro/edición de un lector de códigos de barras — 4
pasos: (1) tipo de conexión, (2) búsqueda de dispositivos disponibles,
(3) información + configuración de escaneo, (4) revisión y guardado.

Reutiliza el patrón `QStackedWidget` de páginas ya usado en otros flujos
multi-página de la app (ej. `SaleView`) en vez de introducir `QWizard`,
que no tiene precedente en esta base de código."""

from __future__ import annotations

import serial.tools.list_ports
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos.modules.barcode_scanners.application.dto import BarcodeScannerDTO
from pos.modules.barcode_scanners.application.providers.registry import CONNECTION_TYPE_LABELS
from pos.modules.barcode_scanners.domain.enums import CaseConversion, ConnectionType

_SERIAL_LIKE = (ConnectionType.USB_SERIAL, ConnectionType.BLUETOOTH_SERIAL, ConnectionType.RS232)
_IP_LIKE = (ConnectionType.TCP_IP, ConnectionType.WIFI)
_HID_LIKE = (ConnectionType.USB_HID, ConnectionType.BLUETOOTH_HID)
_BLUETOOTH_LIKE = (ConnectionType.BLUETOOTH_HID, ConnectionType.BLUETOOTH_SERIAL)

_CASE_LABELS = {
    CaseConversion.NONE: "No convertir",
    CaseConversion.UPPER: "Convertir a MAYÚSCULAS",
    CaseConversion.LOWER: "convertir a minúsculas",
}

_PAGE_TITLES = [
    "Paso 1 de 4 — Tipo de conexión",
    "Paso 2 de 4 — Buscar dispositivos",
    "Paso 3 de 4 — Información del lector",
    "Paso 4 de 4 — Revisión",
]


class BarcodeScannerWizardDialog(QDialog):
    def __init__(
        self,
        existing_device: BarcodeScannerDTO | None = None,
        cash_registers: list[tuple[int, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._existing_device = existing_device
        self._cash_registers = cash_registers or []
        self._values: dict[str, object] | None = None
        self._detected_port: str | None = None
        title = "Editar lector" if existing_device else "Nuevo lector de códigos de barras"
        self.setWindowTitle(title)
        self.setMinimumSize(560, 520)
        self._build_ui()
        if existing_device is not None:
            self._load_existing(existing_device)
        self._go_to_page(0)

    # -- construcción de la UI ------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        self._title_label = QLabel(self)
        self._title_label.setProperty("emphasis", True)
        outer.addWidget(self._title_label)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_step_connection_type())
        self._stack.addWidget(self._build_step_search())
        self._stack.addWidget(self._build_step_info())
        self._stack.addWidget(self._build_step_review())
        outer.addWidget(self._stack)

        nav_row = QHBoxLayout()
        self._back_button = QPushButton("Atrás")
        self._back_button.clicked.connect(self._on_back_clicked)
        nav_row.addWidget(self._back_button)
        nav_row.addStretch()
        self._cancel_button = QPushButton("Cancelar")
        self._cancel_button.clicked.connect(self.reject)
        nav_row.addWidget(self._cancel_button)
        self._next_button = QPushButton("Siguiente")
        self._next_button.clicked.connect(self._on_next_clicked)
        nav_row.addWidget(self._next_button)
        outer.addLayout(nav_row)

    def _build_step_connection_type(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Selecciona el tipo de conexión del lector:"))
        self._connection_group = QButtonGroup(page)
        self._connection_radios: dict[ConnectionType, QRadioButton] = {}
        for connection_type in ConnectionType:
            radio = QRadioButton(CONNECTION_TYPE_LABELS[connection_type], page)
            self._connection_group.addButton(radio)
            self._connection_radios[connection_type] = radio
            layout.addWidget(radio)
        self._connection_radios[ConnectionType.USB_HID].setChecked(True)
        layout.addStretch()
        return page

    def _build_step_search(self) -> QWidget:
        page = QWidget(self)
        self._search_layout = QVBoxLayout(page)
        return page

    def _rebuild_search_step(self) -> None:
        while self._search_layout.count():
            item = self._search_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        connection_type = self._current_connection_type()
        if connection_type in _HID_LIKE:
            self._search_layout.addWidget(
                QLabel(
                    "Los lectores HID no requieren seleccionar un puerto: el dispositivo "
                    "escribe directo donde esté el foco, como un teclado. Continúa al "
                    "siguiente paso."
                )
            )
        elif connection_type in _SERIAL_LIKE:
            self._search_layout.addWidget(QLabel("Puertos disponibles:"))
            self._port_list = QListWidget(self)
            self._search_layout.addWidget(self._port_list)
            search_button = QPushButton("Buscar dispositivos")
            search_button.clicked.connect(self._on_search_ports_clicked)
            self._search_layout.addWidget(search_button)
            self._on_search_ports_clicked()
        else:
            self._search_layout.addWidget(
                QLabel(
                    "No existe un protocolo de descubrimiento genérico por red — ingresa "
                    "la dirección IP y el puerto del lector manualmente en el siguiente paso."
                )
            )
        self._search_layout.addStretch()

    def _on_search_ports_clicked(self) -> None:
        self._port_list.clear()
        ports = serial.tools.list_ports.comports()
        if not ports:
            self._port_list.addItem("No se encontraron puertos disponibles.")
            return
        for port_info in ports:
            item = QListWidgetItem(f"{port_info.device} — {port_info.description}")
            item.setData(Qt.ItemDataRole.UserRole, port_info.device)
            self._port_list.addItem(item)

    def _build_step_info(self) -> QWidget:
        page = QWidget(self)
        outer = QVBoxLayout(page)
        form = QFormLayout()
        outer.addLayout(form)

        self._name_edit = QLineEdit(page)
        self._brand_edit = QLineEdit(page)
        self._model_edit = QLineEdit(page)
        self._serial_edit = QLineEdit(page)
        self._description_edit = QTextEdit(page)
        self._description_edit.setMaximumHeight(60)
        form.addRow("Nombre", self._name_edit)
        form.addRow("Marca", self._brand_edit)
        form.addRow("Modelo", self._model_edit)
        form.addRow("Número de serie", self._serial_edit)
        form.addRow("Descripción", self._description_edit)

        self._cash_register_combo = QComboBox(page)
        self._cash_register_combo.addItem("(sin asignar)", userData=None)
        for register_id, name in self._cash_registers:
            self._cash_register_combo.addItem(name, userData=register_id)
        form.addRow("Caja asignada", self._cash_register_combo)

        self._port_edit = QLineEdit(page)
        self._port_edit.setPlaceholderText("Ej. COM5, /dev/ttyUSB1")
        self._baud_rate_combo = QComboBox(page)
        for rate in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200):
            self._baud_rate_combo.addItem(str(rate), userData=rate)
        self._baud_rate_combo.setCurrentText("9600")
        form.addRow("Puerto", self._port_edit)
        form.addRow("Baud rate", self._baud_rate_combo)

        self._ip_address_edit = QLineEdit(page)
        self._ip_address_edit.setPlaceholderText("Ej. 192.168.1.80")
        self._ip_port_edit = QLineEdit(page)
        self._ip_port_edit.setPlaceholderText("Ej. 9100")
        form.addRow("Dirección IP", self._ip_address_edit)
        form.addRow("Puerto TCP", self._ip_port_edit)

        self._bluetooth_edit = QLineEdit(page)
        self._bluetooth_edit.setPlaceholderText("Dirección/MAC del dispositivo emparejado")
        form.addRow("Bluetooth", self._bluetooth_edit)

        scan_group = QGroupBox("Configuración de lectura", page)
        scan_form = QFormLayout(scan_group)
        self._prefix_edit = QLineEdit(scan_group)
        self._suffix_edit = QLineEdit(scan_group)
        scan_form.addRow("Prefijo", self._prefix_edit)
        scan_form.addRow("Sufijo", self._suffix_edit)
        self._auto_enter_check = QCheckBox("Enviar Enter automáticamente", scan_group)
        self._auto_tab_check = QCheckBox("Enviar Tab automáticamente", scan_group)
        scan_form.addRow(self._auto_enter_check)
        scan_form.addRow(self._auto_tab_check)
        self._min_length_spin = QSpinBox(scan_group)
        self._min_length_spin.setRange(0, 200)
        self._max_length_spin = QSpinBox(scan_group)
        self._max_length_spin.setRange(0, 200)
        scan_form.addRow("Longitud mínima (0 = sin límite)", self._min_length_spin)
        scan_form.addRow("Longitud máxima (0 = sin límite)", self._max_length_spin)
        self._checksum_check = QCheckBox("Validar checksum", scan_group)
        self._strip_special_check = QCheckBox("Eliminar caracteres especiales", scan_group)
        self._ignore_spaces_check = QCheckBox("Ignorar espacios", scan_group)
        scan_form.addRow(self._checksum_check)
        scan_form.addRow(self._strip_special_check)
        scan_form.addRow(self._ignore_spaces_check)
        self._case_combo = QComboBox(scan_group)
        for case, label in _CASE_LABELS.items():
            self._case_combo.addItem(label, userData=case)
        scan_form.addRow("Mayúsculas/minúsculas", self._case_combo)
        self._timeout_spin = QSpinBox(scan_group)
        self._timeout_spin.setRange(1, 5000)
        self._timeout_spin.setValue(50)
        scan_form.addRow("Tiempo máx. entre caracteres (ms)", self._timeout_spin)
        outer.addWidget(scan_group)
        outer.addStretch()
        return page

    def _build_step_review(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        self._review_label = QLabel(page)
        self._review_label.setWordWrap(True)
        layout.addWidget(self._review_label)
        layout.addStretch()
        return page

    # -- navegación -------------------------------------------------------

    def _current_connection_type(self) -> ConnectionType:
        for connection_type, radio in self._connection_radios.items():
            if radio.isChecked():
                return connection_type
        return ConnectionType.USB_HID

    def _go_to_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._title_label.setText(_PAGE_TITLES[index])
        self._back_button.setEnabled(index > 0)
        self._next_button.setText("Guardar" if index == len(_PAGE_TITLES) - 1 else "Siguiente")
        if index == 1:
            self._rebuild_search_step()
        elif index == 2:
            self._apply_detected_port()
            self._update_field_visibility()
        elif index == 3:
            self._review_label.setText(self._build_review_text())

    def _apply_detected_port(self) -> None:
        connection_type = self._current_connection_type()
        if connection_type in _SERIAL_LIKE and hasattr(self, "_port_list"):
            selected = self._port_list.selectedItems()
            if selected:
                self._port_edit.setText(selected[0].data(Qt.ItemDataRole.UserRole) or "")

    def _update_field_visibility(self) -> None:
        connection_type = self._current_connection_type()
        is_serial = connection_type in _SERIAL_LIKE
        is_ip = connection_type in _IP_LIKE
        is_bluetooth = connection_type in _BLUETOOTH_LIKE
        for widget in (self._port_edit, self._baud_rate_combo):
            widget.setVisible(is_serial)
        for widget in (self._ip_address_edit, self._ip_port_edit):
            widget.setVisible(is_ip)
        self._bluetooth_edit.setVisible(is_bluetooth)

    def _on_back_clicked(self) -> None:
        self._go_to_page(self._stack.currentIndex() - 1)

    def _on_next_clicked(self) -> None:
        current = self._stack.currentIndex()
        if current == len(_PAGE_TITLES) - 1:
            self._on_save_clicked()
            return
        if current == 2 and not self._name_edit.text().strip():
            QMessageBox.warning(self, "Error", "El nombre del lector es obligatorio.")
            return
        self._go_to_page(current + 1)

    def _build_review_text(self) -> str:
        connection_type = self._current_connection_type()
        lines = [
            f"Nombre: {self._name_edit.text().strip() or '—'}",
            f"Marca / Modelo: {self._brand_edit.text().strip() or '—'} / "
            f"{self._model_edit.text().strip() or '—'}",
            f"Tipo de conexión: {CONNECTION_TYPE_LABELS[connection_type]}",
        ]
        if connection_type in _SERIAL_LIKE:
            lines.append(f"Puerto: {self._port_edit.text().strip() or '—'}")
        elif connection_type in _IP_LIKE:
            lines.append(
                f"Dirección: {self._ip_address_edit.text().strip() or '—'}:"
                f"{self._ip_port_edit.text().strip() or '—'}"
            )
        lines.append(f"Caja asignada: {self._cash_register_combo.currentText()}")
        return "\n".join(lines)

    # -- guardado -----------------------------------------------------------

    def _on_save_clicked(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre del lector es obligatorio.")
            self._go_to_page(2)
            return
        connection_type = self._current_connection_type()
        port = self._port_edit.text().strip() or None
        if connection_type in _SERIAL_LIKE and not port:
            QMessageBox.warning(
                self, "Error", "El puerto es obligatorio para este tipo de conexión."
            )
            self._go_to_page(2)
            return
        ip_address = self._ip_address_edit.text().strip() or None
        ip_port_text = self._ip_port_edit.text().strip()
        if connection_type in _IP_LIKE and (not ip_address or not ip_port_text):
            QMessageBox.warning(
                self, "Error", "La dirección IP y el puerto son obligatorios para TCP/IP o Wi-Fi."
            )
            self._go_to_page(2)
            return
        try:
            ip_port = int(ip_port_text) if ip_port_text else None
        except ValueError:
            QMessageBox.warning(self, "Error", "El puerto TCP debe ser un número entero.")
            self._go_to_page(2)
            return

        self._values = {
            "name": name,
            "brand": self._brand_edit.text().strip() or None,
            "model": self._model_edit.text().strip() or None,
            "serial_number": self._serial_edit.text().strip() or None,
            "description": self._description_edit.toPlainText().strip() or None,
            "cash_register_id": self._cash_register_combo.currentData(),
            "connection_type": connection_type,
            "port": port,
            "baud_rate": self._baud_rate_combo.currentData(),
            "data_bits": 8,
            "stop_bits": 1,
            "parity": "N",
            "ip_address": ip_address,
            "ip_port": ip_port,
            "bluetooth_address": self._bluetooth_edit.text().strip() or None,
            "prefix": self._prefix_edit.text(),
            "suffix": self._suffix_edit.text(),
            "auto_enter": self._auto_enter_check.isChecked(),
            "auto_tab": self._auto_tab_check.isChecked(),
            "min_length": self._min_length_spin.value() or None,
            "max_length": self._max_length_spin.value() or None,
            "validate_checksum": self._checksum_check.isChecked(),
            "strip_special_chars": self._strip_special_check.isChecked(),
            "convert_case": self._case_combo.currentData(),
            "ignore_spaces": self._ignore_spaces_check.isChecked(),
            "inter_char_timeout_ms": self._timeout_spin.value(),
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values

    def preselect_serial_port(self, port: str) -> None:
        """Usado por la detección automática de dispositivos: precarga el
        asistente en modo USB Serial con el puerto recién detectado."""
        self._connection_radios[ConnectionType.USB_SERIAL].setChecked(True)
        self._port_edit.setText(port)

    # -- edición --------------------------------------------------------

    def _load_existing(self, device: BarcodeScannerDTO) -> None:
        self._connection_radios[device.connection_type].setChecked(True)
        self._name_edit.setText(device.name)
        self._brand_edit.setText(device.brand or "")
        self._model_edit.setText(device.model or "")
        self._serial_edit.setText(device.serial_number or "")
        self._description_edit.setPlainText(device.description or "")
        register_index = self._cash_register_combo.findData(device.cash_register_id)
        if register_index >= 0:
            self._cash_register_combo.setCurrentIndex(register_index)
        self._port_edit.setText(device.port or "")
        if device.baud_rate is not None:
            self._baud_rate_combo.setCurrentText(str(device.baud_rate))
        self._ip_address_edit.setText(device.ip_address or "")
        self._ip_port_edit.setText(str(device.ip_port) if device.ip_port else "")
        self._bluetooth_edit.setText(device.bluetooth_address or "")
        self._prefix_edit.setText(device.prefix)
        self._suffix_edit.setText(device.suffix)
        self._auto_enter_check.setChecked(device.auto_enter)
        self._auto_tab_check.setChecked(device.auto_tab)
        self._min_length_spin.setValue(device.min_length or 0)
        self._max_length_spin.setValue(device.max_length or 0)
        self._checksum_check.setChecked(device.validate_checksum)
        self._strip_special_check.setChecked(device.strip_special_chars)
        self._ignore_spaces_check.setChecked(device.ignore_spaces)
        case_index = self._case_combo.findData(device.convert_case)
        if case_index >= 0:
            self._case_combo.setCurrentIndex(case_index)
        self._timeout_spin.setValue(device.inter_char_timeout_ms)
