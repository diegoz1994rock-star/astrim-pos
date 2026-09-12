"""Ventana de lectura de peso para productos configurados como "Peso"
(`Product.sale_unit is SaleUnit.WEIGHT`).

Al abrirse, inicia lectura continua no bloqueante (`ScaleContinuousReadWorker`)
desde la báscula activa por defecto, vía `ScaleReadService` — el único punto
de lectura de peso de toda la aplicación. Muestra bruto/neto/tara en vivo y
permite aplicar/quitar tara sin cerrar el diálogo. Si no hay báscula
configurada, o falla la conexión/lectura (lo esperable sin hardware real
conectado), cae automáticamente a un campo de peso manual — nunca bloquea la
venta por falta de báscula física, tal como se pidió."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.modules.scales.application.dto import WeightReadingDTO
from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.domain.enums import UnitOfMeasure, WeightEntrySource, WeightReadingStatus
from pos.modules.scales.presentation.scale_continuous_read_worker import ScaleContinuousReadWorker
from pos.shared_ui.formatting import format_currency

_CENTER = Qt.AlignmentFlag.AlignCenter

_STATUS_LABELS: dict[WeightReadingStatus, str] = {
    WeightReadingStatus.STABLE: "✓ Peso estable",
    WeightReadingStatus.UNSTABLE: "Estabilizando…",
    WeightReadingStatus.ZERO: "Peso en cero",
    WeightReadingStatus.NEGATIVE: "⚠ Peso negativo — revisá la báscula",
    WeightReadingStatus.INVALID: "⚠ Lectura inválida",
    WeightReadingStatus.OUT_OF_RANGE: "⚠ Peso fuera del rango permitido para este producto",
}


class ScaleWeightDialog(QDialog):
    """Devuelve `Accepted` con el peso ya confirmado (`weight()`), listo
    para agregarse al carrito/pedido como cantidad — mismo `Decimal` que
    ya acepta `SaleItemInput.quantity`."""

    def __init__(
        self,
        *,
        product_name: str,
        unit_price: Decimal,
        unit_of_measure: str,
        scale_read_service: ScaleReadService,
        min_weight: Decimal | None = None,
        max_weight: Decimal | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Peso — {product_name}")
        self._unit_price = unit_price
        try:
            self._target_unit: UnitOfMeasure | None = UnitOfMeasure(unit_of_measure)
        except ValueError:
            self._target_unit = None
        """`unit_of_measure` es la unidad del producto (siempre "kg" para
        `SaleUnit.WEIGHT`, ver `_UNIT_OF_MEASURE_BY_SALE_UNIT`), que puede no
        coincidir con la unidad configurada en el dispositivo de báscula
        (ej. una báscula en gramos). Se pasa como `target_unit` a
        `ScaleReadService.read()` para que la lectura se convierta antes de
        usarse como cantidad — si no matchea ningún `UnitOfMeasure` conocido,
        se deja sin convertir (comportamiento previo) en vez de romper."""
        self._scale_read_service = scale_read_service
        self._min_weight = min_weight
        self._max_weight = max_weight
        self._weight: Decimal | None = None
        self._device_id: int | None = None
        self._auto_read = False
        self._worker: ScaleContinuousReadWorker | None = None
        self._weight_source = WeightEntrySource.MANUAL
        """Por defecto manual — solo pasa a `SCALE` mientras `_on_reading`
        sigue rellenando el campo con una lectura estable; si el cajero
        edita el campo a mano después (`textEdited`, no `textChanged`, para
        no confundir el `setText` programático con tecleo real) vuelve a
        `MANUAL`, igual que si nunca hubo báscula conectada."""

        layout = QVBoxLayout(self)

        title = QLabel(product_name)
        title.setProperty("emphasis", True)
        title.setAlignment(_CENTER)
        layout.addWidget(title)

        self._status_label = QLabel("")
        self._status_label.setAlignment(_CENTER)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._gross_label = QLabel("Bruto: —")
        self._gross_label.setAlignment(_CENTER)
        layout.addWidget(self._gross_label)
        self._tare_label = QLabel("Tara: —")
        self._tare_label.setAlignment(_CENTER)
        layout.addWidget(self._tare_label)
        self._net_label = QLabel("Neto: —")
        self._net_label.setAlignment(_CENTER)
        self._net_label.setProperty("emphasis", True)
        layout.addWidget(self._net_label)

        tare_actions = QHBoxLayout()
        self._apply_tare_button = QPushButton("Aplicar tara")
        self._apply_tare_button.clicked.connect(self._on_apply_tare_clicked)
        self._apply_tare_button.setEnabled(False)
        self._clear_tare_button = QPushButton("Quitar tara")
        self._clear_tare_button.clicked.connect(self._on_clear_tare_clicked)
        self._clear_tare_button.setEnabled(False)
        tare_actions.addWidget(self._apply_tare_button)
        tare_actions.addWidget(self._clear_tare_button)
        layout.addLayout(tare_actions)

        self._weight_edit = QLineEdit(self)
        self._weight_edit.setAlignment(_CENTER)
        self._weight_edit.setPlaceholderText(f"Peso ({unit_of_measure})")
        layout.addWidget(self._weight_edit)

        self._total_label = QLabel("Total: —")
        self._total_label.setAlignment(_CENTER)
        layout.addWidget(self._total_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._weight_edit.textChanged.connect(self._update_total)
        self._weight_edit.textEdited.connect(self._on_weight_edited_by_hand)
        self._weight_edit.returnPressed.connect(self._on_accept)

        self._start_reading()

    # -- Lectura continua -----------------------------------------------------

    def _start_reading(self) -> None:
        try:
            device = self._scale_read_service.get_active_device()
        except DomainError as error:
            self._fall_back_to_manual(str(error))
            return
        self._device_id = device.id
        self._auto_read = device.auto_read
        self._apply_tare_button.setEnabled(True)
        self._clear_tare_button.setEnabled(True)
        self._launch_worker(float(device.read_frequency_seconds))

    def _launch_worker(self, interval_seconds: float) -> None:
        def _read() -> WeightReadingDTO:
            return self._scale_read_service.read(
                device_id=self._device_id,
                target_unit=self._target_unit,
                product_min_weight=self._min_weight,
                product_max_weight=self._max_weight,
            )

        worker = ScaleContinuousReadWorker(_read, interval_seconds=interval_seconds, parent=self)
        worker.reading.connect(self._on_reading)
        worker.failed.connect(self._fall_back_to_manual)
        self._worker = worker
        worker.start()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait()
            self._worker = None

    def _on_reading(self, reading: WeightReadingDTO) -> None:
        self._status_label.setText(_STATUS_LABELS.get(reading.status, reading.status.value))
        self._gross_label.setText(f"Bruto: {reading.gross_weight} {reading.unit.value}")
        self._tare_label.setText(f"Tara: {reading.tare} {reading.unit.value}")
        self._net_label.setText(f"Neto: {reading.net_weight} {reading.unit.value}")
        if reading.is_stable:
            self._weight_edit.setText(str(reading.net_weight))
            self._weight_source = WeightEntrySource.SCALE
            if self._auto_read:
                self._ok_button.setDefault(True)
                self._ok_button.setFocus()

    def _on_weight_edited_by_hand(self) -> None:
        self._weight_source = WeightEntrySource.MANUAL

    def _fall_back_to_manual(self, message: str) -> None:
        self._stop_worker()
        self._status_label.setText(
            f"Báscula no disponible ({message}). Ingresá el peso manualmente."
        )
        self._apply_tare_button.setEnabled(False)
        self._clear_tare_button.setEnabled(False)
        self._weight_source = WeightEntrySource.MANUAL
        self._weight_edit.setFocus()

    # -- Tara -------------------------------------------------------------------

    def _on_apply_tare_clicked(self) -> None:
        self._stop_worker()
        try:
            reading = self._scale_read_service.apply_tare(self._device_id)
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
        else:
            self._on_reading(reading)
        self._resume_reading()

    def _on_clear_tare_clicked(self) -> None:
        self._stop_worker()
        try:
            self._scale_read_service.clear_tare(self._device_id)
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
        self._resume_reading()

    def _resume_reading(self) -> None:
        try:
            device = self._scale_read_service.get_active_device(self._device_id)
        except DomainError as error:
            self._fall_back_to_manual(str(error))
            return
        self._launch_worker(float(device.read_frequency_seconds))

    # -- Aceptar/cancelar ---------------------------------------------------

    def _update_total(self) -> None:
        try:
            weight = Decimal(self._weight_edit.text())
        except InvalidOperation:
            self._total_label.setText("Total: —")
            return
        self._total_label.setText(f"Total: {format_currency(weight * self._unit_price)}")

    def _on_accept(self) -> None:
        try:
            weight = Decimal(self._weight_edit.text())
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "El peso debe ser un número válido.")
            return
        if weight <= 0:
            QMessageBox.warning(self, "Error", "El peso debe ser mayor que cero.")
            return
        self._weight = weight
        self._stop_worker()
        self.accept()

    def reject(self) -> None:
        self._stop_worker()
        super().reject()

    def weight(self) -> Decimal:
        assert self._weight is not None
        return self._weight

    def weight_entry_source(self) -> WeightEntrySource:
        return self._weight_source
