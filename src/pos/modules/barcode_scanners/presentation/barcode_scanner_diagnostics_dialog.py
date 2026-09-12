"""Diagnóstico de un lector de códigos de barras: estado, puerto,
velocidad, tiempo de respuesta, última comunicación, último error,
fabricante/modelo/firmware/número de serie, cantidad de lecturas y tiempo
conectado — con exportar/copiar."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.modules.barcode_scanners.application.barcode_scanner_service import BarcodeScannerService
from pos.modules.barcode_scanners.application.dto import BarcodeScannerDTO
from pos.modules.barcode_scanners.application.providers.registry import CONNECTION_TYPE_LABELS
from pos.modules.barcode_scanners.domain.enums import BarcodeScannerEventType, ConnectionStatus
from pos.shared_ui.widgets.toast import show_toast
from pos.shared_ui.workers.device_operation_worker import DeviceOperationWorker

_STATUS_LABELS = {
    ConnectionStatus.CONNECTED: "Conectado",
    ConnectionStatus.DISCONNECTED: "Desconectado",
    ConnectionStatus.ERROR: "Error",
}


def _format_datetime(value: object) -> str:
    if value is None:
        return "—"
    return f"{value:%Y-%m-%d %H:%M:%S}"


def _format_elapsed(since: datetime | None) -> str:
    if since is None:
        return "—"
    seconds = int((datetime.now(UTC) - since).total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class BarcodeScannerDiagnosticsDialog(QDialog):
    def __init__(
        self,
        service: BarcodeScannerService,
        device: BarcodeScannerDTO,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._device = device
        self._response_time_ms: int | None = None
        self._last_error: str | None = None
        self._worker: DeviceOperationWorker | None = None
        self.setWindowTitle(f"Diagnóstico — {device.name}")
        self.setMinimumSize(480, 500)
        self._build_ui()
        self._load_last_error()
        self._render()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._form = QFormLayout()
        layout.addLayout(self._form)
        self._fields: dict[str, QLabel] = {}
        for key, label in (
            ("status", "Estado del dispositivo"),
            ("port", "Puerto"),
            ("speed", "Velocidad"),
            ("response_time", "Tiempo de respuesta"),
            ("last_comm", "Última comunicación"),
            ("last_error", "Último error"),
            ("firmware", "Versión / Firmware"),
            ("brand", "Fabricante"),
            ("model", "Modelo"),
            ("serial", "Número de serie"),
            ("scan_count", "Cantidad de lecturas"),
            ("connected_time", "Tiempo conectado"),
        ):
            value_label = QLabel("—", self)
            value_label.setWordWrap(True)
            self._fields[key] = value_label
            self._form.addRow(label, value_label)

        buttons_row = QHBoxLayout()
        self._refresh_button = QPushButton("Actualizar diagnóstico", self)
        self._refresh_button.clicked.connect(self._on_refresh_clicked)
        self._export_button = QPushButton("Exportar diagnóstico", self)
        self._export_button.clicked.connect(self._on_export_clicked)
        self._copy_button = QPushButton("Copiar información", self)
        self._copy_button.clicked.connect(self._on_copy_clicked)
        for button in (self._refresh_button, self._export_button, self._copy_button):
            buttons_row.addWidget(button)
        layout.addLayout(buttons_row)

    def _load_last_error(self) -> None:
        events = self._service.list_events(self._device.id, limit=50)
        error_types = (
            BarcodeScannerEventType.ERROR.value,
            BarcodeScannerEventType.TEST_CONNECTION_FAILED.value,
        )
        error_event = next((e for e in events if e.event_type in error_types), None)
        if error_event is not None:
            when = _format_datetime(error_event.occurred_at)
            self._last_error = f"{error_event.message or '(sin detalle)'} — {when}"

    def _render(self) -> None:
        device = self._device
        self._fields["status"].setText(_STATUS_LABELS[device.connection_status])
        self._fields["port"].setText(device.port or device.ip_address or "—")
        speed = f"{device.baud_rate} baudios" if device.baud_rate else "—"
        self._fields["speed"].setText(speed)
        response_time = (
            f"{self._response_time_ms} ms" if self._response_time_ms is not None else "—"
        )
        self._fields["response_time"].setText(response_time)
        self._fields["last_comm"].setText(_format_datetime(device.last_successful_communication_at))
        self._fields["last_error"].setText(self._last_error or "—")
        self._fields["firmware"].setText(device.firmware_version or "—")
        self._fields["brand"].setText(device.brand or "—")
        self._fields["model"].setText(device.model or "—")
        self._fields["serial"].setText(device.serial_number or "—")
        self._fields["scan_count"].setText(str(device.scan_count))
        self._fields["connected_time"].setText(_format_elapsed(device.connected_since))

    def _on_refresh_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._refresh_button.setEnabled(False)
        start = time.perf_counter()

        def _operation() -> bool:
            return self._service.test_connection(self._device.id)

        def _on_success(_result: object) -> None:
            self._response_time_ms = int((time.perf_counter() - start) * 1000)
            self._refresh_button.setEnabled(True)
            self._reload_device()

        def _on_failure(message: str) -> None:
            self._response_time_ms = int((time.perf_counter() - start) * 1000)
            self._last_error = f"{message} — {_format_datetime(datetime.now(UTC))}"
            self._refresh_button.setEnabled(True)
            self._reload_device()

        worker = DeviceOperationWorker(_operation, self)
        worker.succeeded.connect(_on_success)
        worker.failed.connect(_on_failure)
        self._worker = worker
        worker.start()

    def _reload_device(self) -> None:
        try:
            devices = self._service.list_devices()
        except DomainError:
            self._render()
            return
        updated = next((d for d in devices if d.id == self._device.id), None)
        if updated is not None:
            self._device = updated
        self._render()

    def _report_text(self) -> str:
        device = self._device
        lines = [f"Diagnóstico del lector: {device.name}"]
        lines.append(f"Tipo de conexión: {CONNECTION_TYPE_LABELS[device.connection_type]}")
        for key, label in (
            ("status", "Estado del dispositivo"), ("port", "Puerto"), ("speed", "Velocidad"),
            ("response_time", "Tiempo de respuesta"), ("last_comm", "Última comunicación"),
            ("last_error", "Último error"), ("firmware", "Versión / Firmware"),
            ("brand", "Fabricante"), ("model", "Modelo"), ("serial", "Número de serie"),
            ("scan_count", "Cantidad de lecturas"), ("connected_time", "Tiempo conectado"),
        ):
            lines.append(f"{label}: {self._fields[key].text()}")
        return "\n".join(lines)

    def _on_export_clicked(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, "Exportar diagnóstico", f"diagnostico_{self._device.name}.txt", "Texto (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self._report_text())
        except OSError as error:
            QMessageBox.warning(self, "Error", f"No se pudo exportar el diagnóstico: {error}")
            return
        show_toast(self, "Diagnóstico exportado correctamente.")

    def _on_copy_clicked(self) -> None:
        QApplication.clipboard().setText(self._report_text())
        show_toast(self, "Información copiada al portapapeles.")
