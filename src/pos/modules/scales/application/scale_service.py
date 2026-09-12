"""Casos de uso de administración de básculas y lectura de peso.

Vendedor/Ventas nunca hablan directo con un adaptador concreto (ver
`application/providers/`) — siempre pasan por `read_weight`, que resuelve
la báscula activa por defecto y delega en el adaptador que corresponda a
su `kind` (mismo patrón que `QrPaymentService` para pagos QR)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.scales.application.dto import (
    ScaleCapabilitiesDTO,
    ScaleDeviceConfigDTO,
    ScaleDeviceEventDTO,
)
from pos.modules.scales.application.providers.registry import SIMULATOR_KIND, get_scale_adapter
from pos.modules.scales.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    ScaleDeviceEventType,
    UnitOfMeasure,
)
from pos.modules.scales.infrastructure.models import ScaleDeviceConfig, ScaleDeviceEvent
from pos.modules.scales.infrastructure.repository import ScaleDeviceEventRepository, ScaleRepository

_SERIAL_LIKE = (ConnectionType.SERIAL, ConnectionType.USB)


def _to_dto(device: ScaleDeviceConfig) -> ScaleDeviceConfigDTO:
    return ScaleDeviceConfigDTO(
        id=device.id,
        name=device.name,
        kind=device.kind,
        is_active=device.is_active,
        is_default=device.is_default,
        brand=device.brand,
        model=device.model,
        serial_number=device.serial_number,
        description=device.description,
        location=device.location,
        cash_register_id=device.cash_register_id,
        station_label=device.station_label,
        assigned_user_id=device.assigned_user_id,
        connection_type=device.connection_type,
        port=device.port,
        baud_rate=device.baud_rate,
        data_bits=device.data_bits,
        stop_bits=device.stop_bits,
        parity=device.parity,
        ip_address=device.ip_address,
        ip_port=device.ip_port,
        bluetooth_address=device.bluetooth_address,
        unit_of_measure=device.unit_of_measure,
        decimal_places=device.decimal_places,
        timeout_seconds=device.timeout_seconds,
        read_frequency_seconds=device.read_frequency_seconds,
        auto_read=device.auto_read,
        stability_required=device.stability_required,
        min_stable_seconds=device.min_stable_seconds,
        auto_reconnect=device.auto_reconnect,
        current_tare=device.current_tare,
        simulator_target_weight=device.simulator_target_weight,
        connection_status=device.connection_status,
        last_successful_communication_at=device.last_successful_communication_at,
    )


def _event_to_dto(event: ScaleDeviceEvent) -> ScaleDeviceEventDTO:
    return ScaleDeviceEventDTO(
        id=event.id,
        event_type=event.event_type,
        message=event.message,
        occurred_at=event.occurred_at,
    )


class ScaleService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_devices(self) -> list[ScaleDeviceConfigDTO]:
        with session_scope() as session:
            return [_to_dto(d) for d in ScaleRepository(session).list_all()]

    def get_device(self, device_id: int) -> ScaleDeviceConfigDTO:
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            return _to_dto(device)

    def get_default_device(self) -> ScaleDeviceConfigDTO | None:
        with session_scope() as session:
            device = ScaleRepository(session).get_default()
            return _to_dto(device) if device is not None else None

    def create_device(
        self,
        *,
        name: str,
        kind: str = "generic",
        brand: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        description: str | None = None,
        location: str | None = None,
        cash_register_id: int | None = None,
        station_label: str | None = None,
        assigned_user_id: int | None = None,
        connection_type: ConnectionType = ConnectionType.SERIAL,
        port: str | None = None,
        baud_rate: int | None = 9600,
        data_bits: int | None = None,
        stop_bits: int | None = None,
        parity: str | None = None,
        ip_address: str | None = None,
        ip_port: int | None = None,
        bluetooth_address: str | None = None,
        unit_of_measure: UnitOfMeasure = UnitOfMeasure.KG,
        decimal_places: int = 3,
        timeout_seconds: int = 2,
        read_frequency_seconds: int = 1,
        auto_read: bool = False,
        stability_required: bool = True,
        min_stable_seconds: Decimal = Decimal("0.50"),
        auto_reconnect: bool = True,
        simulator_target_weight: Decimal | None = None,
    ) -> ScaleDeviceConfigDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la báscula es obligatorio.")
        port = _validate_connection_params(kind, connection_type, port, ip_address, ip_port)
        with session_scope() as session:
            repo = ScaleRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe una báscula llamada '{name}'.")
            had_any = len(repo.list_all()) > 0
            device = repo.create(
                name=name,
                kind=kind,
                brand=brand,
                model=model,
                serial_number=serial_number,
                description=description,
                location=location,
                cash_register_id=cash_register_id,
                station_label=station_label,
                assigned_user_id=assigned_user_id,
                connection_type=connection_type,
                port=port,
                baud_rate=baud_rate,
                data_bits=data_bits,
                stop_bits=stop_bits,
                parity=parity,
                ip_address=ip_address,
                ip_port=ip_port,
                bluetooth_address=bluetooth_address,
                unit_of_measure=unit_of_measure,
                decimal_places=decimal_places,
                timeout_seconds=timeout_seconds,
                read_frequency_seconds=read_frequency_seconds,
                auto_read=auto_read,
                stability_required=stability_required,
                min_stable_seconds=min_stable_seconds,
                auto_reconnect=auto_reconnect,
            )
            if simulator_target_weight is not None:
                repo.set_simulator_target_weight(device, simulator_target_weight)
            if not had_any:
                repo.set_default(device)
            return _to_dto(device)

    def update_device(
        self,
        device_id: int,
        *,
        name: str,
        kind: str = "generic",
        brand: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        description: str | None = None,
        location: str | None = None,
        cash_register_id: int | None = None,
        station_label: str | None = None,
        assigned_user_id: int | None = None,
        connection_type: ConnectionType = ConnectionType.SERIAL,
        port: str | None = None,
        baud_rate: int | None = 9600,
        data_bits: int | None = None,
        stop_bits: int | None = None,
        parity: str | None = None,
        ip_address: str | None = None,
        ip_port: int | None = None,
        bluetooth_address: str | None = None,
        unit_of_measure: UnitOfMeasure = UnitOfMeasure.KG,
        decimal_places: int = 3,
        timeout_seconds: int = 2,
        read_frequency_seconds: int = 1,
        auto_read: bool = False,
        stability_required: bool = True,
        min_stable_seconds: Decimal = Decimal("0.50"),
        auto_reconnect: bool = True,
        simulator_target_weight: Decimal | None = None,
    ) -> ScaleDeviceConfigDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la báscula es obligatorio.")
        with session_scope() as session:
            repo = ScaleRepository(session)
            device = repo.get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            # El puerto interno del simulador (`SIM-<id>`) se conserva entre
            # ediciones para no reiniciar su estado de rampa por error.
            port = _validate_connection_params(
                kind, connection_type, port, ip_address, ip_port,
                existing_simulator_port=device.port,
            )
            existing = repo.get_by_name(name)
            if existing is not None and existing.id != device_id:
                raise ConflictError(f"Ya existe una báscula llamada '{name}'.")
            repo.update(
                device,
                name=name,
                kind=kind,
                brand=brand,
                model=model,
                serial_number=serial_number,
                description=description,
                location=location,
                cash_register_id=cash_register_id,
                station_label=station_label,
                assigned_user_id=assigned_user_id,
                connection_type=connection_type,
                port=port,
                baud_rate=baud_rate,
                data_bits=data_bits,
                stop_bits=stop_bits,
                parity=parity,
                ip_address=ip_address,
                ip_port=ip_port,
                bluetooth_address=bluetooth_address,
                unit_of_measure=unit_of_measure,
                decimal_places=decimal_places,
                timeout_seconds=timeout_seconds,
                read_frequency_seconds=read_frequency_seconds,
                auto_read=auto_read,
                stability_required=stability_required,
                min_stable_seconds=min_stable_seconds,
                auto_reconnect=auto_reconnect,
            )
            if simulator_target_weight is not None:
                repo.set_simulator_target_weight(device, simulator_target_weight)
            return _to_dto(device)

    def set_device_active(self, device_id: int, is_active: bool) -> ScaleDeviceConfigDTO:
        with session_scope() as session:
            repo = ScaleRepository(session)
            device = repo.get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            repo.set_active(device, is_active)
            return _to_dto(device)

    def set_default_device(self, device_id: int) -> ScaleDeviceConfigDTO:
        with session_scope() as session:
            repo = ScaleRepository(session)
            device = repo.get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            if not device.is_active:
                raise BusinessRuleViolationError(
                    "No se puede marcar como predeterminada una báscula inactiva."
                )
            repo.clear_default_flag_for_all()
            repo.set_default(device)
            return _to_dto(device)

    def delete_device(self, device_id: int) -> None:
        with session_scope() as session:
            repo = ScaleRepository(session)
            device = repo.get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            repo.delete(device)

    def get_capabilities(self, device_id: int) -> ScaleCapabilitiesDTO:
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            kind = device.kind
        adapter = get_scale_adapter(kind)
        return ScaleCapabilitiesDTO(
            supports_tare=adapter.supports_tare, supports_calibration=adapter.supports_calibration
        )

    def test_connection(self, device_id: int) -> bool:
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            kind, port, baud_rate, connection_type, simulated_target = (
                device.kind, device.port, device.baud_rate, device.connection_type,
                device.simulator_target_weight,
            )
        try:
            self._require_serial_like(kind, connection_type)
            result = get_scale_adapter(kind).test_connection(
                port=port, baud_rate=baud_rate, simulated_target=simulated_target
            )
        except BusinessRuleViolationError as error:
            self._log_event(device_id, ScaleDeviceEventType.TEST_CONNECTION_FAILED, str(error))
            raise
        self._log_event(device_id, ScaleDeviceEventType.TEST_CONNECTION_OK, None)
        return result

    def connect(self, device_id: int) -> ScaleDeviceConfigDTO:
        """Prueba la conexión y, si funciona, marca el dispositivo como
        `CONNECTED` (queda como último estado conocido, ver
        `ConnectionStatus`). El adaptador genérico no mantiene un socket/
        puerto abierto entre llamadas — cada operación (leer peso, tara)
        abre y cierra su propia conexión — así que "conectar" es, en la
        práctica, verificar y registrar que el dispositivo respondió."""
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            kind, port, baud_rate, connection_type, simulated_target = (
                device.kind, device.port, device.baud_rate, device.connection_type,
                device.simulator_target_weight,
            )
        try:
            self._require_serial_like(kind, connection_type)
            get_scale_adapter(kind).test_connection(
                port=port, baud_rate=baud_rate, simulated_target=simulated_target
            )
        except BusinessRuleViolationError as error:
            self._set_status(device_id, ConnectionStatus.ERROR)
            self._log_event(device_id, ScaleDeviceEventType.ERROR, str(error))
            raise
        self._set_status(device_id, ConnectionStatus.CONNECTED)
        self._log_event(device_id, ScaleDeviceEventType.CONNECTED, None)
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            assert device is not None
            return _to_dto(device)

    def disconnect(self, device_id: int) -> ScaleDeviceConfigDTO:
        self._set_status(device_id, ConnectionStatus.DISCONNECTED)
        self._log_event(device_id, ScaleDeviceEventType.DISCONNECTED, None)
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            return _to_dto(device)

    def read_weight(self) -> Decimal:
        """Lee el peso desde la báscula activa marcada como predeterminada.
        Si no hay ninguna configurada, o falla la conexión/lectura, levanta
        `BusinessRuleViolationError` — `ScaleWeightDialog` lo usa para caer
        a ingreso manual del peso, tal como se pidió."""
        device = self.get_default_device()
        if device is None:
            raise BusinessRuleViolationError(
                "No hay ninguna báscula configurada como predeterminada."
            )
        return self._read_weight_from(device)

    def read_weight_for_device(self, device_id: int) -> Decimal:
        """Lee el peso de una báscula específica (no necesariamente la
        predeterminada) — usado desde el panel de pruebas, donde el
        encargado puede querer probar cualquier dispositivo registrado."""
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            dto = _to_dto(device)
        return self._read_weight_from(dto)

    def _read_weight_from(self, device: ScaleDeviceConfigDTO) -> Decimal:
        try:
            self._require_serial_like(device.kind, device.connection_type)
            weight = get_scale_adapter(device.kind).read_weight(
                port=device.port,
                baud_rate=device.baud_rate,
                simulated_target=device.simulator_target_weight,
            )
        except BusinessRuleViolationError as error:
            self._log_event(device.id, ScaleDeviceEventType.READ_FAILED, str(error))
            raise
        self._log_event(device.id, ScaleDeviceEventType.READ_SUCCESS, None)
        return weight

    def tare(self, device_id: int) -> None:
        """Tara de hardware — solo la usan adaptadores de marca que sí
        soportan un comando de tara remota (ninguno hoy: el genérico y el
        simulador no). La tara que de verdad usa la UI es la universal por
        software (`ScaleReadService.apply_tare`), que funciona sin importar
        esta capacidad."""
        device_dto, kind = self._get_dto_and_kind(device_id)
        adapter = get_scale_adapter(kind)
        if not adapter.supports_tare:
            raise BusinessRuleViolationError(
                "El adaptador actual de esta báscula no soporta tara remota de hardware."
            )
        try:
            self._require_serial_like(kind, device_dto.connection_type)
            adapter.tare(port=device_dto.port, baud_rate=device_dto.baud_rate)
        except BusinessRuleViolationError as error:
            self._log_event(device_id, ScaleDeviceEventType.ERROR, str(error))
            raise
        self._log_event(device_id, ScaleDeviceEventType.TARE, None)

    def calibrate(self, device_id: int) -> None:
        device_dto, kind = self._get_dto_and_kind(device_id)
        adapter = get_scale_adapter(kind)
        if not adapter.supports_calibration:
            raise BusinessRuleViolationError(
                "El adaptador actual de esta báscula no soporta calibración remota."
            )
        try:
            self._require_serial_like(kind, device_dto.connection_type)
            adapter.calibrate(port=device_dto.port, baud_rate=device_dto.baud_rate)
        except BusinessRuleViolationError as error:
            self._log_event(device_id, ScaleDeviceEventType.ERROR, str(error))
            raise
        self._log_event(device_id, ScaleDeviceEventType.CALIBRATION, None)

    def list_events(self, device_id: int, limit: int = 50) -> list[ScaleDeviceEventDTO]:
        with session_scope() as session:
            events = ScaleDeviceEventRepository(session).list_for_device(device_id, limit)
            return [_event_to_dto(e) for e in events]

    def set_simulator_target_weight(self, device_id: int, weight: Decimal) -> ScaleDeviceConfigDTO:
        if weight < 0:
            raise BusinessRuleViolationError("El peso simulado no puede ser negativo.")
        with session_scope() as session:
            repo = ScaleRepository(session)
            device = repo.get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            if device.kind != SIMULATOR_KIND:
                raise BusinessRuleViolationError(
                    "Solo se puede fijar un peso simulado en una báscula de tipo Simulador."
                )
            repo.set_simulator_target_weight(device, weight)
            return _to_dto(device)

    def set_current_tare(self, device_id: int, tare: Decimal) -> ScaleDeviceConfigDTO:
        """Persiste el offset de tara — lo usa `ScaleReadService`, no se
        expone directamente como una operación de UI (ver `apply_tare`/
        `clear_tare` ahí)."""
        with session_scope() as session:
            repo = ScaleRepository(session)
            device = repo.get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            repo.set_current_tare(device, tare)
            return _to_dto(device)

    def reset_stale_connections(self) -> None:
        """Fuerza `DISCONNECTED` en todas las básculas al arrancar la app —
        ninguna conexión real puede sobrevivir un reinicio del proceso."""
        with session_scope() as session:
            ScaleRepository(session).reset_all_connection_statuses()

    # -- internos -----------------------------------------------------------

    def _require_serial_like(self, kind: str, connection_type: ConnectionType) -> None:
        if kind == SIMULATOR_KIND:
            return
        if connection_type not in _SERIAL_LIKE:
            raise BusinessRuleViolationError(
                f"El adaptador genérico solo soporta conexión USB/Serial — "
                f"'{connection_type.value}' requiere un adaptador específico del fabricante."
            )

    def _get_dto_and_kind(self, device_id: int) -> tuple[ScaleDeviceConfigDTO, str]:
        with session_scope() as session:
            device = ScaleRepository(session).get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            return _to_dto(device), device.kind

    def _set_status(self, device_id: int, status: ConnectionStatus) -> None:
        with session_scope() as session:
            repo = ScaleRepository(session)
            device = repo.get(device_id)
            if device is None:
                raise NotFoundError(f"No existe la báscula con id={device_id}.")
            repo.set_connection_status(device, status, occurred_at=datetime.now(UTC))

    def _log_event(
        self, device_id: int, event_type: ScaleDeviceEventType, message: str | None
    ) -> None:
        with session_scope() as session:
            ScaleDeviceEventRepository(session).create(
                scale_device_id=device_id,
                event_type=event_type,
                message=message,
                occurred_at=datetime.now(UTC),
            )


def _validate_connection_params(
    kind: str,
    connection_type: ConnectionType,
    port: str | None,
    ip_address: str | None,
    ip_port: int | None,
    *,
    existing_simulator_port: str | None = None,
) -> str | None:
    """Valida que los parámetros obligatorios del tipo de conexión elegido
    estén presentes, y normaliza `port`. Bluetooth no tiene validación
    obligatoria propia todavía (el adaptador genérico no lo soporta, ver
    `ScaleService._require_serial_like`). Un dispositivo `Simulador` no usa
    puerto real — se le asigna uno interno autogenerado (`SIM-<uuid>`), que
    `SimulatorScaleProvider` usa solo como clave de su estado en memoria,
    nunca visible en la UI ni editable por el usuario."""
    if kind == SIMULATOR_KIND:
        return existing_simulator_port or f"SIM-{uuid.uuid4().hex[:8]}"
    if connection_type in _SERIAL_LIKE:
        if not port or not port.strip():
            raise BusinessRuleViolationError(
                "El puerto es obligatorio para conexión USB/Serial."
            )
        return port.strip()
    if connection_type in (ConnectionType.ETHERNET, ConnectionType.WIFI):
        if not ip_address or not ip_address.strip() or not ip_port:
            raise BusinessRuleViolationError(
                "La dirección IP y el puerto son obligatorios para conexión Ethernet/Wi-Fi."
            )
    return port.strip() if port else None
