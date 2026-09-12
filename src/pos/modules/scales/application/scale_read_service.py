"""Servicio centralizado de lectura de peso — el equivalente de
`BarcodeReadService` para básculas. Vendedor/Ventas, el panel de pruebas y
el diálogo de peso nunca hablan directo con `ScaleService`/un adaptador
concreto para leer un peso: siempre pasan por acá, que resuelve la
báscula (por id o la predeterminada), aplica la tara universal por
software, clasifica la lectura, detecta estabilidad, reintenta una vez si
la conexión falla y `auto_reconnect` está activo, y registra cada intento
(éxito o error) en el historial centralizado (`scale_weight_reads`).

Deliberadamente no sabe nada de Qt/PySide — la lectura continua no
bloqueante vive en la capa de presentación (`ScaleContinuousReadWorker`),
que llama a `read()` repetidamente."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.scales.application.dto import (
    ScaleDeviceConfigDTO,
    ScaleDiagnosticsDTO,
    ScaleReadLogEntryDTO,
    WeightReadingDTO,
)
from pos.modules.scales.application.scale_service import ScaleService
from pos.modules.scales.domain.enums import (
    ConnectionStatus,
    ScaleDeviceEventType,
    UnitOfMeasure,
    WeightReadingStatus,
)
from pos.modules.scales.domain.weight_reading import (
    StabilityTracker,
    classify_reading,
    convert_weight,
)
from pos.modules.scales.infrastructure.repository import (
    ScaleDeviceEventRepository,
    ScaleRepository,
    ScaleWeightReadRepository,
)


class ScaleReadService:
    def __init__(
        self, scale_service: ScaleService, product_service: ProductManagementService
    ) -> None:
        self._scale_service = scale_service
        self._product_service = product_service
        self._trackers: dict[int, StabilityTracker] = {}

    # -- Lectura centralizada -------------------------------------------------

    def read(
        self,
        *,
        device_id: int | None = None,
        target_unit: UnitOfMeasure | None = None,
        product_min_weight: Decimal | None = None,
        product_max_weight: Decimal | None = None,
        product_id: int | None = None,
        user_id: int | None = None,
        username: str | None = None,
        cash_register_id: int | None = None,
        cash_register_name: str | None = None,
    ) -> WeightReadingDTO:
        device = self._resolve_device(device_id)
        started_at = time.monotonic()
        occurred_at = datetime.now(UTC)
        reconnected = False

        try:
            gross = self._scale_service.read_weight_for_device(device.id)
        except BusinessRuleViolationError as error:
            if device.auto_reconnect:
                try:
                    self._scale_service.connect(device.id)
                    reconnected = True
                    gross = self._scale_service.read_weight_for_device(device.id)
                    self._log_device_event(
                        device.id, ScaleDeviceEventType.RECONNECTED,
                        "Reconexión automática exitosa tras un fallo de lectura.",
                    )
                except BusinessRuleViolationError:
                    self._record_history(
                        device=device, product_id=product_id, user_id=user_id,
                        username=username, cash_register_id=cash_register_id,
                        cash_register_name=cash_register_name, gross_weight=None,
                        net_weight=None, status=WeightReadingStatus.INVALID, is_stable=False,
                        duration_ms=self._elapsed_ms(started_at), error_message=str(error),
                        reconnected=reconnected, occurred_at=occurred_at,
                    )
                    raise
            else:
                self._record_history(
                    device=device, product_id=product_id, user_id=user_id, username=username,
                    cash_register_id=cash_register_id, cash_register_name=cash_register_name,
                    gross_weight=None, net_weight=None, status=WeightReadingStatus.INVALID,
                    is_stable=False, duration_ms=self._elapsed_ms(started_at),
                    error_message=str(error), reconnected=False, occurred_at=occurred_at,
                )
                raise

        unit = target_unit or device.unit_of_measure
        if unit is not device.unit_of_measure:
            gross = convert_weight(gross, device.unit_of_measure, unit)
        tare = (
            convert_weight(device.current_tare, device.unit_of_measure, unit)
            if unit is not device.unit_of_measure
            else device.current_tare
        )
        net = gross - tare

        tracker = self._tracker_for(device)
        content_status = classify_reading(
            net, min_weight=product_min_weight, max_weight=product_max_weight
        )
        if content_status is not None:
            tracker.reset()
            status = content_status
            is_stable = False
        elif not device.stability_required:
            status = WeightReadingStatus.STABLE
            is_stable = True
        else:
            is_stable = tracker.push(net, now=occurred_at)
            status = WeightReadingStatus.STABLE if is_stable else WeightReadingStatus.UNSTABLE

        duration_ms = self._elapsed_ms(started_at)
        self._record_history(
            device=device, product_id=product_id, user_id=user_id, username=username,
            cash_register_id=cash_register_id, cash_register_name=cash_register_name,
            gross_weight=gross, net_weight=net, status=status, is_stable=is_stable,
            duration_ms=duration_ms, error_message=None, reconnected=reconnected,
            occurred_at=occurred_at, tare=tare,
        )
        return WeightReadingDTO(
            device_id=device.id, device_name=device.name, gross_weight=gross, net_weight=net,
            tare=tare, unit=unit, status=status, is_stable=is_stable, duration_ms=duration_ms,
            reconnected=reconnected, read_at=occurred_at,
        )

    def get_active_device(self, device_id: int | None = None) -> ScaleDeviceConfigDTO:
        """Resuelve la báscula que se va a usar (la indicada o la
        predeterminada) — expuesto para que la presentación pueda leer su
        configuración (`auto_read`, `read_frequency_seconds`, etc.) antes de
        iniciar una sesión de lectura continua (`ScaleContinuousReadWorker`)."""
        return self._resolve_device(device_id)

    # -- Tara universal por software ------------------------------------------

    def apply_tare(self, device_id: int | None = None) -> WeightReadingDTO:
        """Pone en cero el peso neto tomando la lectura bruta actual como
        offset — funciona con cualquier adaptador, incluidos los que no
        soportan un comando de tara remota de hardware (ver
        `ScaleProvider.supports_tare`)."""
        device = self._resolve_device(device_id)
        gross = self._scale_service.read_weight_for_device(device.id)
        self._scale_service.set_current_tare(device.id, gross)
        self._log_device_event(
            device.id, ScaleDeviceEventType.TARE,
            f"Tara aplicada: {gross} {device.unit_of_measure.value}.",
        )
        self._tracker_for(device).reset()
        return WeightReadingDTO(
            device_id=device.id, device_name=device.name, gross_weight=gross,
            net_weight=Decimal("0"), tare=gross, unit=device.unit_of_measure,
            status=WeightReadingStatus.STABLE, is_stable=True, duration_ms=0,
            reconnected=False, read_at=datetime.now(UTC),
        )

    def clear_tare(self, device_id: int | None = None) -> None:
        device = self._resolve_device(device_id)
        self._scale_service.set_current_tare(device.id, Decimal("0"))
        self._log_device_event(device.id, ScaleDeviceEventType.TARE, "Tara removida.")
        self._tracker_for(device).reset()

    # -- Diagnóstico y log ------------------------------------------------------

    def get_diagnostics(self, device_id: int | None = None) -> ScaleDiagnosticsDTO:
        device: ScaleDeviceConfigDTO | None = None
        if device_id is not None:
            device = self._scale_service.get_device(device_id)
        with session_scope() as session:
            repo = ScaleWeightReadRepository(session)
            last = repo.most_recent(device_id)
            total = repo.count_total(device_id)
            errors = repo.count_errors(device_id)
            reconnections = repo.count_reconnections(device_id)
            durations = repo.recent_durations_ms(device_id)

        average_duration_ms = sum(durations) / len(durations) if durations else None
        connected = device is not None and device.connection_status is ConnectionStatus.CONNECTED
        uptime_seconds: float | None = None
        if device is not None and device.last_successful_communication_at is not None:
            uptime_seconds = (
                datetime.now(UTC) - device.last_successful_communication_at
            ).total_seconds()

        return ScaleDiagnosticsDTO(
            connected=connected,
            port=device.port if device is not None else None,
            baud_rate=device.baud_rate if device is not None else None,
            current_weight=last.net_weight if last is not None else None,
            last_weight=last.net_weight if last is not None else None,
            last_read_at=last.occurred_at if last is not None else None,
            last_error=last.error_message if last is not None else None,
            total_reads=total,
            error_count=errors,
            reconnection_count=reconnections,
            average_read_duration_ms=average_duration_ms,
            uptime_seconds=uptime_seconds,
        )

    def list_recent_reads(
        self, device_id: int | None = None, limit: int = 200
    ) -> list[ScaleReadLogEntryDTO]:
        with session_scope() as session:
            entries = ScaleWeightReadRepository(session).list_recent(device_id, limit)
            device_names = {d.id: d.name for d in ScaleRepository(session).list_all()}
            product_ids = [entry.product_id for entry in entries if entry.product_id is not None]

        product_names = self._product_service.get_product_names(product_ids) if product_ids else {}
        return [
            ScaleReadLogEntryDTO(
                id=entry.id,
                device_name=(
                    device_names.get(entry.scale_device_id) if entry.scale_device_id else None
                ),
                product_name=product_names.get(entry.product_id) if entry.product_id else None,
                gross_weight=entry.gross_weight,
                net_weight=entry.net_weight,
                unit=entry.unit,
                status=entry.status,
                is_stable=entry.is_stable,
                username=entry.username,
                cash_register_name=entry.cash_register_name,
                duration_ms=entry.duration_ms,
                error_message=entry.error_message,
                reconnected=entry.reconnected,
                occurred_at=entry.occurred_at,
            )
            for entry in entries
        ]

    # -- internos -----------------------------------------------------------

    def _resolve_device(self, device_id: int | None) -> ScaleDeviceConfigDTO:
        if device_id is not None:
            return self._scale_service.get_device(device_id)
        device = self._scale_service.get_default_device()
        if device is None:
            raise BusinessRuleViolationError(
                "No hay ninguna báscula configurada como predeterminada."
            )
        return device

    def _tracker_for(self, device: ScaleDeviceConfigDTO) -> StabilityTracker:
        tolerance = Decimal(1).scaleb(-device.decimal_places)
        tracker = self._trackers.get(device.id)
        if (
            tracker is None
            or tracker.tolerance != tolerance
            or tracker.min_stable_seconds != device.min_stable_seconds
        ):
            tracker = StabilityTracker(
                tolerance=tolerance, min_stable_seconds=device.min_stable_seconds
            )
            self._trackers[device.id] = tracker
        return tracker

    def _elapsed_ms(self, started_at: float) -> int:
        return max(0, round((time.monotonic() - started_at) * 1000))

    def _log_device_event(
        self, device_id: int, event_type: ScaleDeviceEventType, message: str | None
    ) -> None:
        with session_scope() as session:
            ScaleDeviceEventRepository(session).create(
                scale_device_id=device_id,
                event_type=event_type,
                message=message,
                occurred_at=datetime.now(UTC),
            )

    def _record_history(
        self,
        *,
        device: ScaleDeviceConfigDTO,
        product_id: int | None,
        user_id: int | None,
        username: str | None,
        cash_register_id: int | None,
        cash_register_name: str | None,
        gross_weight: Decimal | None,
        net_weight: Decimal | None,
        status: WeightReadingStatus,
        is_stable: bool,
        duration_ms: int,
        error_message: str | None,
        reconnected: bool,
        occurred_at: datetime,
        tare: Decimal | None = None,
    ) -> None:
        with session_scope() as session:
            ScaleWeightReadRepository(session).insert_read(
                scale_device_id=device.id,
                product_id=product_id,
                user_id=user_id,
                username=username,
                cash_register_id=cash_register_id,
                cash_register_name=cash_register_name,
                gross_weight=gross_weight,
                net_weight=net_weight,
                tare=tare if tare is not None else device.current_tare,
                unit=device.unit_of_measure,
                status=status,
                is_stable=is_stable,
                duration_ms=duration_ms,
                error_message=error_message,
                reconnected=reconnected,
                occurred_at=occurred_at,
            )
