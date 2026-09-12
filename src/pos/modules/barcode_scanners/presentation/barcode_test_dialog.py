"""Diálogo "Probar lector" — no exige ningún dispositivo registrado, a
diferencia del panel de pruebas por-dispositivo (`barcode_scanner_test_panel_dialog.py`,
que sigue existiendo para la sección secundaria de inventario). Cualquier
lector HID conectado ya funciona acá con solo escanear."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.modules.barcode_scanners.application.dto import BarcodeReadResultDTO
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource

_SYMBOLOGY_LABELS = {
    "ean13": "EAN-13", "ean8": "EAN-8", "upc_a": "UPC-A", "upc_e": "UPC-E",
    "code39": "Code 39", "code93": "Code 93", "code128": "Code 128", "codabar": "Codabar",
    "itf": "Interleaved 2 of 5", "msi": "MSI", "gs1_128": "GS1-128",
    "datamatrix": "DataMatrix", "pdf417": "PDF417", "qr": "QR Code", "aztec": "Aztec",
    "unknown": "Desconocido",
}


class BarcodeTestDialog(QDialog):
    def __init__(
        self, barcode_read_service: BarcodeReadService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._service = barcode_read_service
        self.setWindowTitle("Probar lector")
        self.setMinimumSize(420, 360)

        layout = QVBoxLayout(self)
        self._status_label = QLabel("Escanee un código...", self)
        self._status_label.setProperty("emphasis", True)
        layout.addWidget(self._status_label)

        self._scan_edit = QLineEdit(self)
        self._scan_edit.setPlaceholderText("Este campo tiene el foco — solo escanee")
        self._scan_edit.setMinimumHeight(56)
        font = self._scan_edit.font()
        font.setPointSize(font.pointSize() + 4)
        self._scan_edit.setFont(font)
        self._scan_edit.returnPressed.connect(self._on_scan)
        layout.addWidget(self._scan_edit)

        result_group = QGroupBox("Última lectura", self)
        form = QFormLayout(result_group)
        self._code_label = QLabel("—", result_group)
        self._length_label = QLabel("—", result_group)
        self._type_label = QLabel("—", result_group)
        self._time_label = QLabel("—", result_group)
        form.addRow("Código leído:", self._code_label)
        form.addRow("Longitud:", self._length_label)
        form.addRow("Tipo:", self._type_label)
        form.addRow("Hora:", self._time_label)
        layout.addWidget(result_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._scan_edit.setFocus()

    def _on_scan(self) -> None:
        raw = self._scan_edit.text()
        self._scan_edit.clear()
        self._scan_edit.setFocus()
        if not raw.strip():
            return
        result = self._service.resolve_scan(raw, source=BarcodeReadSource.TEST_PANEL)
        self._display_result(result)

    def _display_result(self, result: BarcodeReadResultDTO) -> None:
        if result.ignored:
            self._status_label.setText(f"⏳ Esperando lectura... ({result.reason})")
            return
        self._code_label.setText(result.code)
        self._length_label.setText(str(len(result.code)))
        symbology_label = _SYMBOLOGY_LABELS.get(result.symbology.value, result.symbology.value)
        self._type_label.setText(symbology_label)
        self._time_label.setText(f"{datetime.now():%H:%M:%S}")
        self._status_label.setText("✅ Lectura correcta")
