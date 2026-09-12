"""Panel de pruebas de una báscula (Administración → Dispositivos → Báscula
electrónica): lectura continua en vivo, tara (universal por software,
funciona con cualquier adaptador) y calibración. Calibrar queda
deshabilitado cuando el adaptador actual no lo soporta — nunca oculto, para
que quede claro que es una limitación del adaptador, no un bug. Para
dispositivos "Simulador" agrega un control de peso objetivo, que permite
probar todo el flujo de estabilidad/tara sin báscula física conectada."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.modules.scales.application.dto import ScaleCapabilitiesDTO, WeightReadingDTO
from pos.modules.scales.application.providers.registry import SIMULATOR_KIND
from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.application.scale_service import ScaleService
from pos.modules.scales.domain.enums import WeightReadingStatus
from pos.modules.scales.presentation.scale_continuous_read_worker import ScaleContinuousReadWorker
from pos.shared_ui.widgets.toast import show_toast

_STATUS_LABELS = {
    WeightReadingStatus.STABLE: "✓ Estable",
    WeightReadingStatus.UNSTABLE: "Estabilizando…",
    WeightReadingStatus.ZERO: "Cero",
    WeightReadingStatus.NEGATIVE: "⚠ Negativo",
    WeightReadingStatus.INVALID: "⚠ Inválido",
    WeightReadingStatus.OUT_OF_RANGE: "⚠ Fuera de rango",
}


class ScaleTestPanelDialog(QDialog):
    def __init__(
        self,
        service: ScaleService,
        scale_read_service: ScaleReadService,
        device_id: int,
        device_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._scale_read_service = scale_read_service
        self._device_id = device_id
        self._is_simulator = False
        self._worker: ScaleContinuousReadWorker | None = None
        self.setWindowTitle(f"Pruebas — {device_name}")
        self.setMinimumWidth(380)
        self._build_ui()
        self._load_capabilities()
        self._load_simulator_controls()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        self._weight_label = QLabel("Peso: —")
        self._weight_label.setProperty("emphasis", True)
        layout.addWidget(self._weight_label)
        self._tare_label = QLabel("Tara: —")
        layout.addWidget(self._tare_label)

        read_actions = QHBoxLayout()
        self._start_button = QPushButton("Iniciar lectura")
        self._start_button.clicked.connect(self._on_start_clicked)
        self._stop_button = QPushButton("Detener")
        self._stop_button.clicked.connect(self._on_stop_clicked)
        self._stop_button.setEnabled(False)
        read_actions.addWidget(self._start_button)
        read_actions.addWidget(self._stop_button)
        layout.addLayout(read_actions)

        actions = QHBoxLayout()
        self._tare_button = QPushButton("Aplicar tara")
        self._tare_button.clicked.connect(self._on_tare_clicked)
        self._clear_tare_button = QPushButton("Quitar tara")
        self._clear_tare_button.clicked.connect(self._on_clear_tare_clicked)
        self._calibrate_button = QPushButton("Calibrar")
        self._calibrate_button.clicked.connect(self._on_calibrate_clicked)
        actions.addWidget(self._tare_button)
        actions.addWidget(self._clear_tare_button)
        actions.addWidget(self._calibrate_button)
        layout.addLayout(actions)

        self._simulator_row = QHBoxLayout()
        self._simulator_target_edit = QLineEdit(self)
        self._simulator_target_edit.setPlaceholderText("Peso simulado objetivo, ej. 1.250")
        self._simulator_apply_button = QPushButton("Fijar peso simulado")
        self._simulator_apply_button.clicked.connect(self._on_set_simulator_target_clicked)
        self._simulator_row.addWidget(self._simulator_target_edit)
        self._simulator_row.addWidget(self._simulator_apply_button)
        layout.addLayout(self._simulator_row)

        self._capabilities_label = QLabel("")
        self._capabilities_label.setProperty("role", "secondary")
        self._capabilities_label.setWordWrap(True)
        layout.addWidget(self._capabilities_label)

    def _load_capabilities(self) -> None:
        try:
            capabilities: ScaleCapabilitiesDTO = self._service.get_capabilities(self._device_id)
        except DomainError as error:
            self._show_error(str(error))
            capabilities = ScaleCapabilitiesDTO(supports_tare=False, supports_calibration=False)
        # La tara del panel siempre está habilitada: es universal por
        # software (`ScaleReadService.apply_tare`), no depende de que el
        # adaptador soporte un comando de tara remota de hardware.
        self._calibrate_button.setEnabled(capabilities.supports_calibration)
        if not capabilities.supports_calibration:
            self._capabilities_label.setText(
                "El adaptador actual de esta báscula no soporta calibración remota — "
                "requiere un adaptador específico del fabricante."
            )

    def _load_simulator_controls(self) -> None:
        try:
            device = self._service.get_device(self._device_id)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._is_simulator = device.kind == SIMULATOR_KIND
        self._simulator_target_edit.setVisible(self._is_simulator)
        self._simulator_apply_button.setVisible(self._is_simulator)
        if self._is_simulator and device.simulator_target_weight is not None:
            self._simulator_target_edit.setText(str(device.simulator_target_weight))

    # -- Lectura continua -----------------------------------------------------

    def _on_start_clicked(self) -> None:
        try:
            device = self._service.get_device(self._device_id)
        except DomainError as error:
            self._show_error(str(error))
            return

        def _read() -> WeightReadingDTO:
            return self._scale_read_service.read(device_id=self._device_id)

        worker = ScaleContinuousReadWorker(
            _read, interval_seconds=float(device.read_frequency_seconds), parent=self
        )
        worker.reading.connect(self._on_reading)
        worker.failed.connect(self._on_read_failed)
        self._worker = worker
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        worker.start()

    def _on_stop_clicked(self) -> None:
        self._stop_worker()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait()
            self._worker = None
        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)

    def _on_reading(self, reading: WeightReadingDTO) -> None:
        self._status_label.setText(_STATUS_LABELS.get(reading.status, reading.status.value))
        self._weight_label.setText(f"Peso: {reading.net_weight} {reading.unit.value}")
        self._tare_label.setText(f"Tara: {reading.tare} {reading.unit.value}")
        if reading.is_stable:
            self._start_button.setEnabled(True)
            self._stop_button.setEnabled(False)
            self._worker = None

    def _on_read_failed(self, message: str) -> None:
        self._show_error(message)
        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._worker = None

    # -- Tara / calibración -------------------------------------------------

    def _on_tare_clicked(self) -> None:
        try:
            reading = self._scale_read_service.apply_tare(self._device_id)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._on_reading(reading)
        self._show_info("Tara aplicada.")

    def _on_clear_tare_clicked(self) -> None:
        try:
            self._scale_read_service.clear_tare(self._device_id)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._weight_label.setText("Peso: —")
        self._tare_label.setText("Tara: —")
        self._show_info("Tara removida.")

    def _on_calibrate_clicked(self) -> None:
        try:
            self._service.calibrate(self._device_id)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._show_info("Calibración realizada.")

    def _on_set_simulator_target_clicked(self) -> None:
        try:
            weight = Decimal(self._simulator_target_edit.text() or "0")
        except InvalidOperation:
            self._show_error("El peso simulado debe ser un número válido.")
            return
        try:
            self._service.set_simulator_target_weight(self._device_id, weight)
        except DomainError as error:
            self._show_error(str(error))
            return
        self._show_info(f"Peso simulado fijado en {weight}.")

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)

    def reject(self) -> None:
        self._stop_worker()
        super().reject()
