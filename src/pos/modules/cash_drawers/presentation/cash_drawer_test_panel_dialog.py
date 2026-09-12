"""Panel de pruebas de un cajón monedero: "Probar apertura" abre de verdad
el cajón en un hilo en background (`DeviceOperationWorker`, mismo patrón que
báscula/código de barras) para no congelar la interfaz, con estados en
vivo ("Conectando…" → "Enviando comando…" → resultado + tiempo). La
apertura de prueba pasa por `CashDrawerService.open_drawer` — la misma y
única fuente de verdad que usa Ventas — así que también exige un usuario
autenticado y queda registrada en el historial como apertura manual."""

from __future__ import annotations

import time

from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from pos.core.security.session import SessionManager
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_drawers.domain.enums import CashDrawerOpeningKind
from pos.shared_ui.workers.device_operation_worker import DeviceOperationWorker

_TEST_REASON = "Prueba desde el panel de pruebas"


class CashDrawerTestPanelDialog(QDialog):
    def __init__(
        self,
        service: CashDrawerService,
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
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        self._open_button = QPushButton("Probar apertura")
        self._open_button.clicked.connect(self._on_open_clicked)
        layout.addWidget(self._open_button)

        self._status_label = QLabel("")
        self._status_label.setProperty("emphasis", True)
        layout.addWidget(self._status_label)

        self._result_label = QLabel("")
        self._result_label.setWordWrap(True)
        self._result_label.setProperty("role", "secondary")
        layout.addWidget(self._result_label)

    def _on_open_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        current_user = self._session_manager.current
        if current_user is None:
            QMessageBox.warning(
                self, "Error", "Debes iniciar sesión para probar la apertura del cajón."
            )
            return

        self._open_button.setEnabled(False)
        self._status_label.setText("Conectando…")
        self._result_label.setText("")
        started_at = time.monotonic()

        def _operation() -> bool:
            self._status_label.setText("Enviando comando…")
            return self._service.open_drawer(
                self._device_id,
                user_id=current_user.user_id,
                username=current_user.username,
                opening_kind=CashDrawerOpeningKind.MANUAL,
                reason=_TEST_REASON,
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
        self._open_button.setEnabled(True)
        if success:
            self._status_label.setText("✔ Apertura correcta")
            self._result_label.setText(f"Tiempo de respuesta: {elapsed_ms} ms")
        else:
            self._status_label.setText("❌ Error")
            self._result_label.setText(f"{message} — {elapsed_ms} ms")

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()
        super().reject()
