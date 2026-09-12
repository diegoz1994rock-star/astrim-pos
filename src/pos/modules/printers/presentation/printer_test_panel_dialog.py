"""Panel de pruebas de una impresora: "Probar impresora" imprime de verdad
una página de prueba en un hilo en background (`DeviceOperationWorker`,
mismo patrón que báscula/cajón/código de barras) para no congelar la
interfaz. Pasa por `PrinterService.print_test_page` — la misma y única
fuente de verdad de "imprimir" que usa Ventas — así que también exige un
usuario autenticado y queda registrada en el historial."""

from __future__ import annotations

import platform
import time
from datetime import datetime

from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from pos.core.security.session import SessionManager
from pos.modules.printers.application.printer_service import PrinterService
from pos.shared_ui.workers.device_operation_worker import DeviceOperationWorker


class PrinterTestPanelDialog(QDialog):
    def __init__(
        self,
        service: PrinterService,
        session_manager: SessionManager,
        device_id: int,
        device_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._session_manager = session_manager
        self._device_id = device_id
        self._worker: DeviceOperationWorker | None = None
        self.setWindowTitle(f"Pruebas — {device_name}")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        info = QLabel(f"Sistema: {platform.platform()}\nFecha: {datetime.now():%Y-%m-%d %H:%M:%S}")
        info.setProperty("role", "secondary")
        layout.addWidget(info)

        self._print_button = QPushButton("Probar impresora")
        self._print_button.clicked.connect(self._on_print_clicked)
        layout.addWidget(self._print_button)

        self._status_label = QLabel("")
        self._status_label.setProperty("emphasis", True)
        layout.addWidget(self._status_label)

        self._result_label = QLabel("")
        self._result_label.setWordWrap(True)
        self._result_label.setProperty("role", "secondary")
        layout.addWidget(self._result_label)

    def _on_print_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        current_user = self._session_manager.current
        if current_user is None:
            QMessageBox.warning(
                self, "Error", "Debes iniciar sesión para probar la impresora."
            )
            return

        self._print_button.setEnabled(False)
        self._status_label.setText("Enviando página de prueba…")
        self._result_label.setText("")
        started_at = time.monotonic()

        def _operation() -> bool:
            return self._service.print_test_page(
                self._device_id, user_id=current_user.user_id, username=current_user.username
            )

        def _on_success(_result: object) -> None:
            self._on_finished(started_at, success=True)

        def _on_failure(message: str) -> None:
            self._on_finished(started_at, success=False, message=message)

        worker = DeviceOperationWorker(_operation, self)
        worker.succeeded.connect(_on_success)
        worker.failed.connect(_on_failure)
        self._worker = worker
        worker.start()

    def _on_finished(
        self, started_at: float, *, success: bool, message: str | None = None
    ) -> None:
        elapsed_ms = round((time.monotonic() - started_at) * 1000)
        self._print_button.setEnabled(True)
        if success:
            self._status_label.setText("✔ Página de prueba enviada")
            self._result_label.setText(f"Tiempo de respuesta: {elapsed_ms} ms")
        else:
            self._status_label.setText("❌ Error")
            self._result_label.setText(f"{message} — {elapsed_ms} ms")

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()
        super().reject()
