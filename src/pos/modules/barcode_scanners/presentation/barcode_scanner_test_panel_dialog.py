"""Panel de pruebas de un lector de códigos de barras: estado en vivo,
lectura real y "Simular lectura" — un código simulado entra por
exactamente el mismo camino de procesamiento que uno real (ver
`BarcodeScannerService._process_scan`), y ambos se guardan en el
historial."""

from __future__ import annotations

import time

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.modules.barcode_scanners.application.barcode_scanner_service import BarcodeScannerService
from pos.modules.barcode_scanners.application.dto import ScanOutcomeDTO
from pos.modules.barcode_scanners.domain.enums import ConnectionType
from pos.shared_ui.workers.device_operation_worker import DeviceOperationWorker

_HID_LIKE = (ConnectionType.USB_HID, ConnectionType.BLUETOOTH_HID)

_SYMBOLOGY_LABELS = {
    "ean13": "EAN-13", "ean8": "EAN-8", "upc_a": "UPC-A", "upc_e": "UPC-E",
    "code39": "Code 39", "code93": "Code 93", "code128": "Code 128", "codabar": "Codabar",
    "itf": "Interleaved 2 of 5", "msi": "MSI", "gs1_128": "GS1-128",
    "datamatrix": "DataMatrix", "pdf417": "PDF417", "qr": "QR Code", "aztec": "Aztec",
    "unknown": "Desconocido",
}


class SimulateScanDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Simular lectura")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Escribe el código a simular:"))
        self._code_edit = QLineEdit(self)
        layout.addWidget(self._code_edit)
        buttons_row = QVBoxLayout()
        ok_button = QPushButton("Aceptar", self)
        ok_button.clicked.connect(self._on_accept)
        cancel_button = QPushButton("Cancelar", self)
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(ok_button)
        buttons_row.addWidget(cancel_button)
        layout.addLayout(buttons_row)
        self._code_edit.setFocus()

    def _on_accept(self) -> None:
        if not self._code_edit.text().strip():
            QMessageBox.warning(self, "Error", "Escribe un código para simular.")
            return
        self.accept()

    def code(self) -> str:
        return self._code_edit.text().strip()


class BarcodeScannerTestPanelDialog(QDialog):
    def __init__(
        self,
        service: BarcodeScannerService,
        device_id: int,
        device_name: str,
        connection_type: ConnectionType,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._device_id = device_id
        self._connection_type = connection_type
        self._hid_start: float | None = None
        self._worker: DeviceOperationWorker | None = None
        self.setWindowTitle(f"Pruebas — {device_name}")
        self.setMinimumSize(480, 420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._status_label = QLabel("Estado: Esperando lectura…", self)
        self._status_label.setProperty("emphasis", True)
        layout.addWidget(self._status_label)

        if self._connection_type in _HID_LIKE:
            self._scan_edit = QLineEdit(self)
            self._scan_edit.setPlaceholderText("Haz clic aquí y escanea con el lector…")
            self._scan_edit.setMinimumHeight(72)
            font = self._scan_edit.font()
            font.setPointSize(font.pointSize() + 4)
            self._scan_edit.setFont(font)
            self._scan_edit.textEdited.connect(self._on_hid_text_edited)
            self._scan_edit.returnPressed.connect(self._on_hid_scan)
            layout.addWidget(self._scan_edit)
            self._scan_edit.setFocus()
        else:
            self._read_button = QPushButton("Leer", self)
            self._read_button.setMinimumHeight(56)
            self._read_button.clicked.connect(self._on_read_clicked)
            layout.addWidget(self._read_button)

        self._simulate_button = QPushButton("Simular lectura", self)
        self._simulate_button.clicked.connect(self._on_simulate_clicked)
        layout.addWidget(self._simulate_button)

        result_group = QGroupBox("Resultado de la lectura", self)
        form = QFormLayout(result_group)
        self._code_label = QLabel("—", result_group)
        self._type_label = QLabel("—", result_group)
        self._length_label = QLabel("—", result_group)
        self._time_label = QLabel("—", result_group)
        self._duration_label = QLabel("—", result_group)
        self._validity_label = QLabel("—", result_group)
        form.addRow("Código leído:", self._code_label)
        form.addRow("Tipo de código:", self._type_label)
        form.addRow("Cantidad de caracteres:", self._length_label)
        form.addRow("Hora:", self._time_label)
        form.addRow("Tiempo de lectura:", self._duration_label)
        form.addRow("Validez:", self._validity_label)
        layout.addWidget(result_group)

    def _on_hid_text_edited(self, text: str) -> None:
        if text and self._hid_start is None:
            self._hid_start = time.perf_counter()
        elif not text:
            self._hid_start = None

    def _on_hid_scan(self) -> None:
        raw = self._scan_edit.text()
        start = self._hid_start
        self._scan_edit.clear()
        self._hid_start = None
        if not raw:
            return
        duration_ms = int((time.perf_counter() - start) * 1000) if start is not None else 0
        try:
            outcome = self._service.process_hid_scan(self._device_id, raw, duration_ms)
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
            return
        self._display_outcome(outcome)

    def _on_read_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._status_label.setText("Estado: Leyendo…")
        self._read_button.setEnabled(False)
        worker = DeviceOperationWorker(lambda: self._service.read_code(self._device_id), self)
        worker.succeeded.connect(self._on_read_succeeded)
        worker.failed.connect(self._on_read_failed)
        self._worker = worker
        worker.start()

    def _on_read_succeeded(self, outcome: object) -> None:
        self._read_button.setEnabled(True)
        self._display_outcome(outcome)  # type: ignore[arg-type]

    def _on_read_failed(self, message: str) -> None:
        self._read_button.setEnabled(True)
        self._status_label.setText("Estado: Esperando lectura…")
        QMessageBox.warning(self, "Error", message)

    def _on_simulate_clicked(self) -> None:
        dialog = SimulateScanDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            outcome = self._service.simulate_scan(self._device_id, dialog.code())
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
            return
        self._display_outcome(outcome)

    def _display_outcome(self, outcome: ScanOutcomeDTO) -> None:
        parsed = outcome.parsed
        status = "Estado: Conectado" if not outcome.is_simulated else "Estado: Simulado"
        self._status_label.setText(status)
        self._code_label.setText(parsed.code)
        symbology_label = _SYMBOLOGY_LABELS.get(parsed.symbology.value, parsed.symbology.value)
        self._type_label.setText(symbology_label)
        self._length_label.setText(str(len(parsed.code)))
        self._time_label.setText(f"{outcome.occurred_at.astimezone():%H:%M:%S}")
        if outcome.is_simulated:
            self._duration_label.setText("— (simulado)")
        else:
            self._duration_label.setText(f"{outcome.duration_ms} ms")
        if parsed.is_valid:
            self._validity_label.setText("Válido")
        else:
            self._validity_label.setText("Inválido: " + "; ".join(parsed.errors))
