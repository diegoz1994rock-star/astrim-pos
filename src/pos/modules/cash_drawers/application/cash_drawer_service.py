"""Casos de uso de administración de cajones monederos.

Toda apertura del cajón —automática tras una venta/abono en efectivo, o
manual desde el botón "Abrir cajón"— pasa exclusivamente por
`open_drawer`/`open_drawer_for_cash_register`: es la única fuente de
verdad de "abrir el cajón" en toda la aplicación (no existe ninguna otra
implementación en paralelo). Cada cajón usa su propia conexión
(USB/Serial/Bluetooth/Ethernet/Wi-Fi) configurada directamente."""

from __future__ import annotations

import platform
import time
from datetime import UTC, datetime

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.cash_drawers.application.dto import (
    CashDrawerDiagnosticsDTO,
    CashDrawerDTO,
    CashDrawerEventDTO,
)
from pos.modules.cash_drawers.application.providers.base import DrawerConnectionParams
from pos.modules.cash_drawers.application.providers.registry import get_drawer_adapter
from pos.modules.cash_drawers.domain.enums import (
    CashDrawerEventType,
    CashDrawerOpeningKind,
    ConnectionStatus,
    ConnectionType,
    OpeningType,
)
from pos.modules.cash_drawers.domain.escpos_command import build_kick_command
from pos.modules.cash_drawers.infrastructure.models import CashDrawer, CashDrawerEvent
from pos.modules.cash_drawers.infrastructure.repository import (
    CashDrawerEventRepository,
    CashDrawerRepository,
)
from pos.modules.cash_register.application.cash_register_service import CashRegisterService

_SERIAL_LIKE = (ConnectionType.SERIAL, ConnectionType.USB)
_IP_LIKE = (ConnectionType.ETHERNET, ConnectionType.WIFI)


def _to_dto(drawer: CashDrawer) -> CashDrawerDTO:
    return CashDrawerDTO(
        id=drawer.id,
        name=drawer.name,
        kind=drawer.kind,
        is_active=drawer.is_active,
        is_default=drawer.is_default,
        brand=drawer.brand,
        model=drawer.model,
        serial_number=drawer.serial_number,
        location=drawer.location,
        opening_type=drawer.opening_type,
        linked_printer_name=drawer.linked_printer_name,
        connection_type=drawer.connection_type,
        port=drawer.port,
        baud_rate=drawer.baud_rate,
        ip_address=drawer.ip_address,
        ip_port=drawer.ip_port,
        timeout_seconds=drawer.timeout_seconds,
        pulse_count=drawer.pulse_count,
        pulse_duration_ms=drawer.pulse_duration_ms,
        custom_command_hex=drawer.custom_command_hex,
        cash_register_id=drawer.cash_register_id,
        auto_open_after_sale=drawer.auto_open_after_sale,
        connection_status=drawer.connection_status,
        last_successful_communication_at=drawer.last_successful_communication_at,
    )


def _event_to_dto(event: CashDrawerEvent) -> CashDrawerEventDTO:
    return CashDrawerEventDTO(
        id=event.id,
        event_type=event.event_type,
        message=event.message,
        occurred_at=event.occurred_at,
        opening_kind=event.opening_kind,
        user_id=event.user_id,
        username=event.username,
        cash_register_id=event.cash_register_id,
        cash_register_name=event.cash_register_name,
        workstation=event.workstation,
        branch_location=event.branch_location,
        sale_id=event.sale_id,
        invoice_id=event.invoice_id,
        debt_payment_id=event.debt_payment_id,
        reason=event.reason,
        response_time_ms=event.response_time_ms,
        port_used=event.port_used,
        ip_address_used=event.ip_address_used,
        ip_port_used=event.ip_port_used,
        model_snapshot=event.model_snapshot,
        brand_snapshot=event.brand_snapshot,
    )


class CashDrawerService:
    def __init__(
        self,
        event_bus: EventBus,
        cash_register_service: CashRegisterService,
    ) -> None:
        self._event_bus = event_bus
        self._cash_register_service = cash_register_service

    def list_devices(self) -> list[CashDrawerDTO]:
        with session_scope() as session:
            return [_to_dto(d) for d in CashDrawerRepository(session).list_all()]

    def get_device(self, device_id: int) -> CashDrawerDTO:
        return self._get_dto(device_id)

    def create_device(
        self,
        *,
        name: str,
        kind: str = "generic",
        brand: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        location: str | None = None,
        opening_type: OpeningType = OpeningType.DIRECT_SERIAL,
        linked_printer_name: str | None = None,
        connection_type: ConnectionType = ConnectionType.SERIAL,
        port: str | None = None,
        baud_rate: int | None = 9600,
        ip_address: str | None = None,
        ip_port: int | None = None,
        timeout_seconds: int = 2,
        pulse_count: int = 1,
        pulse_duration_ms: int = 50,
        custom_command_hex: str | None = None,
        cash_register_id: int | None = None,
        auto_open_after_sale: bool = False,
    ) -> CashDrawerDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del cajón es obligatorio.")
        port = _validate_connection_params(connection_type, port, ip_address, ip_port)
        _validate_pulse_config(pulse_count, pulse_duration_ms, custom_command_hex)
        with session_scope() as session:
            repo = CashDrawerRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe un cajón llamado '{name}'.")
            if (
                cash_register_id is not None
                and repo.get_by_cash_register_id(cash_register_id) is not None
            ):
                raise ConflictError(
                    "Esa caja ya tiene un cajón asignado — una caja solo puede tener un cajón."
                )
            had_any = len(repo.list_all()) > 0
            drawer = repo.create(
                name=name, kind=kind, brand=brand, model=model, serial_number=serial_number,
                location=location, opening_type=opening_type,
                linked_printer_name=linked_printer_name,
                connection_type=connection_type, port=port, baud_rate=baud_rate,
                ip_address=ip_address, ip_port=ip_port, timeout_seconds=timeout_seconds,
                pulse_count=pulse_count, pulse_duration_ms=pulse_duration_ms,
                custom_command_hex=custom_command_hex, cash_register_id=cash_register_id,
                auto_open_after_sale=auto_open_after_sale,
            )
            if not had_any:
                repo.set_default(drawer)
            return _to_dto(drawer)

    def update_device(
        self,
        device_id: int,
        *,
        name: str,
        kind: str = "generic",
        brand: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        location: str | None = None,
        opening_type: OpeningType = OpeningType.DIRECT_SERIAL,
        linked_printer_name: str | None = None,
        connection_type: ConnectionType = ConnectionType.SERIAL,
        port: str | None = None,
        baud_rate: int | None = 9600,
        ip_address: str | None = None,
        ip_port: int | None = None,
        timeout_seconds: int = 2,
        pulse_count: int = 1,
        pulse_duration_ms: int = 50,
        custom_command_hex: str | None = None,
        cash_register_id: int | None = None,
        auto_open_after_sale: bool = False,
    ) -> CashDrawerDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del cajón es obligatorio.")
        port = _validate_connection_params(connection_type, port, ip_address, ip_port)
        _validate_pulse_config(pulse_count, pulse_duration_ms, custom_command_hex)
        with session_scope() as session:
            repo = CashDrawerRepository(session)
            drawer = repo.get(device_id)
            if drawer is None:
                raise NotFoundError(f"No existe el cajón con id={device_id}.")
            existing = repo.get_by_name(name)
            if existing is not None and existing.id != device_id:
                raise ConflictError(f"Ya existe un cajón llamado '{name}'.")
            if cash_register_id is not None:
                other = repo.get_by_cash_register_id(cash_register_id)
                if other is not None and other.id != device_id:
                    raise ConflictError(
                        "Esa caja ya tiene un cajón asignado — una caja solo puede tener un cajón."
                    )
            repo.update(
                drawer, name=name, kind=kind, brand=brand, model=model,
                serial_number=serial_number, location=location, opening_type=opening_type,
                linked_printer_name=linked_printer_name, connection_type=connection_type,
                port=port, baud_rate=baud_rate, ip_address=ip_address, ip_port=ip_port,
                timeout_seconds=timeout_seconds, pulse_count=pulse_count,
                pulse_duration_ms=pulse_duration_ms, custom_command_hex=custom_command_hex,
                cash_register_id=cash_register_id, auto_open_after_sale=auto_open_after_sale,
            )
            return _to_dto(drawer)

    def set_device_active(self, device_id: int, is_active: bool) -> CashDrawerDTO:
        with session_scope() as session:
            repo = CashDrawerRepository(session)
            drawer = repo.get(device_id)
            if drawer is None:
                raise NotFoundError(f"No existe el cajón con id={device_id}.")
            repo.set_active(drawer, is_active)
            return _to_dto(drawer)

    def set_default_device(self, device_id: int) -> CashDrawerDTO:
        with session_scope() as session:
            repo = CashDrawerRepository(session)
            drawer = repo.get(device_id)
            if drawer is None:
                raise NotFoundError(f"No existe el cajón con id={device_id}.")
            if not drawer.is_active:
                raise BusinessRuleViolationError(
                    "No se puede marcar como predeterminado un cajón inactivo."
                )
            repo.clear_default_flag_for_all()
            repo.set_default(drawer)
            return _to_dto(drawer)

    def delete_device(self, device_id: int) -> None:
        with session_scope() as session:
            repo = CashDrawerRepository(session)
            drawer = repo.get(device_id)
            if drawer is None:
                raise NotFoundError(f"No existe el cajón con id={device_id}.")
            repo.delete(drawer)

    def test_connection(self, device_id: int) -> bool:
        dto = self._get_dto(device_id)
        params = self._resolve_params(dto)
        try:
            result = get_drawer_adapter(dto.kind).test_connection(params)
        except BusinessRuleViolationError as error:
            self._log_event(dto, CashDrawerEventType.TEST_CONNECTION_FAILED, str(error))
            raise
        self._log_event(dto, CashDrawerEventType.TEST_CONNECTION_OK, None)
        return result

    def connect(self, device_id: int) -> CashDrawerDTO:
        dto = self._get_dto(device_id)
        params = self._resolve_params(dto)
        try:
            get_drawer_adapter(dto.kind).test_connection(params)
        except BusinessRuleViolationError as error:
            self._set_status(device_id, ConnectionStatus.ERROR)
            self._log_event(dto, CashDrawerEventType.ERROR, str(error))
            raise
        self._set_status(device_id, ConnectionStatus.CONNECTED)
        self._log_event(dto, CashDrawerEventType.CONNECTED, None)
        return self._get_dto(device_id)

    def disconnect(self, device_id: int) -> CashDrawerDTO:
        dto = self._get_dto(device_id)
        self._set_status(device_id, ConnectionStatus.DISCONNECTED)
        self._log_event(dto, CashDrawerEventType.DISCONNECTED, None)
        return self._get_dto(device_id)

    def open_drawer(
        self,
        device_id: int,
        *,
        user_id: int,
        username: str | None = None,
        opening_kind: CashDrawerOpeningKind = CashDrawerOpeningKind.MANUAL,
        sale_id: int | None = None,
        invoice_id: int | None = None,
        debt_payment_id: int | None = None,
        reason: str | None = None,
    ) -> bool:
        """Único método de todo el sistema que envía un pulso real de
        apertura. Exige un usuario autenticado (`user_id`) — nunca hay
        aperturas anónimas — y, si el cajón tiene una caja asignada, exige
        que su sesión esté abierta antes de enviar el comando."""
        if user_id is None:
            raise BusinessRuleViolationError(
                "No se puede abrir el cajón sin un usuario autenticado."
            )
        dto = self._get_dto(device_id)
        if not dto.is_active:
            raise BusinessRuleViolationError(f"El cajón '{dto.name}' está desactivado.")
        register_name = self._require_open_session_if_assigned(dto)
        params = self._resolve_params(dto)

        started_at = time.monotonic()
        try:
            result = get_drawer_adapter(dto.kind).open_drawer(params)
        except BusinessRuleViolationError as error:
            self._log_open_event(
                dto, CashDrawerEventType.OPEN_FAILED, str(error),
                opening_kind=opening_kind, user_id=user_id, username=username,
                cash_register_name=register_name, sale_id=sale_id, invoice_id=invoice_id,
                debt_payment_id=debt_payment_id, reason=reason,
                response_time_ms=self._elapsed_ms(started_at), params=params,
            )
            raise
        self._log_open_event(
            dto, CashDrawerEventType.OPENED, None,
            opening_kind=opening_kind, user_id=user_id, username=username,
            cash_register_name=register_name, sale_id=sale_id, invoice_id=invoice_id,
            debt_payment_id=debt_payment_id, reason=reason,
            response_time_ms=self._elapsed_ms(started_at), params=params,
        )
        return result

    def open_drawer_for_cash_register(
        self,
        cash_register_id: int,
        *,
        user_id: int,
        username: str | None = None,
        opening_kind: CashDrawerOpeningKind = CashDrawerOpeningKind.AUTOMATIC,
        sale_id: int | None = None,
        invoice_id: int | None = None,
        debt_payment_id: int | None = None,
        reason: str | None = None,
    ) -> bool | None:
        """Resuelve el cajón activo con apertura automática habilitada
        para esa caja y lo abre — punto de enganche real desde Ventas
        (venta con componente en efectivo) y Facturación (abono en
        efectivo). Devuelve `None` (no `False`) cuando la caja no tiene
        ningún cajón configurado para apertura automática — no todo
        negocio tiene uno, y eso no es un error."""
        with session_scope() as session:
            drawer = next(
                (
                    d
                    for d in CashDrawerRepository(session).list_all()
                    if d.cash_register_id == cash_register_id
                    and d.is_active
                    and d.auto_open_after_sale
                ),
                None,
            )
            device_id = drawer.id if drawer is not None else None
        if device_id is None:
            return None
        return self.open_drawer(
            device_id, user_id=user_id, username=username, opening_kind=opening_kind,
            sale_id=sale_id, invoice_id=invoice_id, debt_payment_id=debt_payment_id,
            reason=reason,
        )

    def get_diagnostics(self, device_id: int) -> CashDrawerDiagnosticsDTO:
        dto = self._get_dto(device_id)
        with session_scope() as session:
            repo = CashDrawerEventRepository(session)
            last_opened = repo.most_recent_opened(device_id)
            last_error_event = repo.most_recent_error(device_id)
            total_opens = repo.count_by_event_type(device_id, CashDrawerEventType.OPENED)
            error_count = repo.count_by_event_type(
                device_id, CashDrawerEventType.OPEN_FAILED
            ) + repo.count_by_event_type(device_id, CashDrawerEventType.ERROR)
            average_response_time_ms = repo.average_response_time_ms(device_id)
        return CashDrawerDiagnosticsDTO(
            connected=dto.connection_status is ConnectionStatus.CONNECTED,
            port=dto.port,
            ip_address=dto.ip_address,
            ip_port=dto.ip_port,
            kind=dto.kind,
            brand=dto.brand,
            model=dto.model,
            last_opened_at=last_opened.occurred_at if last_opened is not None else None,
            average_response_time_ms=average_response_time_ms,
            total_opens=total_opens,
            error_count=error_count,
            last_error=last_error_event.message if last_error_event is not None else None,
        )

    def list_events(self, device_id: int, limit: int = 50) -> list[CashDrawerEventDTO]:
        with session_scope() as session:
            events = CashDrawerEventRepository(session).list_for_device(device_id, limit)
            return [_event_to_dto(e) for e in events]

    def reset_stale_connections(self) -> None:
        with session_scope() as session:
            CashDrawerRepository(session).reset_all_connection_statuses()

    # -- internos -------------------------------------------------------

    def _resolve_params(self, dto: CashDrawerDTO) -> DrawerConnectionParams:
        return DrawerConnectionParams(
            port=dto.port, baud_rate=dto.baud_rate, ip_address=dto.ip_address,
            ip_port=dto.ip_port, pulse_count=dto.pulse_count,
            pulse_duration_ms=dto.pulse_duration_ms, custom_command_hex=dto.custom_command_hex,
            timeout_seconds=dto.timeout_seconds,
        )

    def _require_open_session_if_assigned(self, dto: CashDrawerDTO) -> str | None:
        """Si el cajón está asignado a una caja, exige que su sesión esté
        abierta antes de enviar cualquier comando — nunca abrir con caja
        cerrada. Cajones sin caja asignada (uso administrativo/pruebas) no
        tienen sesión que verificar. Devuelve el nombre de la caja para el
        registro de auditoría."""
        if dto.cash_register_id is None:
            return None
        session = self._cash_register_service.get_open_session(dto.cash_register_id)
        if session is None:
            raise BusinessRuleViolationError(
                f"No hay un turno de caja abierto en '{dto.name}' — abre la caja antes "
                "de abrir el cajón."
            )
        return session.cash_register_name

    def _get_dto(self, device_id: int) -> CashDrawerDTO:
        with session_scope() as session:
            drawer = CashDrawerRepository(session).get(device_id)
            if drawer is None:
                raise NotFoundError(f"No existe el cajón con id={device_id}.")
            return _to_dto(drawer)

    def _set_status(self, device_id: int, status: ConnectionStatus) -> None:
        with session_scope() as session:
            repo = CashDrawerRepository(session)
            drawer = repo.get(device_id)
            if drawer is None:
                raise NotFoundError(f"No existe el cajón con id={device_id}.")
            repo.set_connection_status(drawer, status, occurred_at=datetime.now(UTC))

    def _elapsed_ms(self, started_at: float) -> int:
        return max(0, round((time.monotonic() - started_at) * 1000))

    def _log_event(
        self, dto: CashDrawerDTO, event_type: CashDrawerEventType, message: str | None
    ) -> None:
        with session_scope() as session:
            CashDrawerEventRepository(session).create(
                cash_drawer_id=dto.id, event_type=event_type, message=message,
                occurred_at=datetime.now(UTC),
            )

    def _log_open_event(
        self,
        dto: CashDrawerDTO,
        event_type: CashDrawerEventType,
        message: str | None,
        *,
        opening_kind: CashDrawerOpeningKind,
        user_id: int,
        username: str | None,
        cash_register_name: str | None,
        sale_id: int | None,
        invoice_id: int | None,
        debt_payment_id: int | None,
        reason: str | None,
        response_time_ms: int,
        params: DrawerConnectionParams,
    ) -> None:
        with session_scope() as session:
            CashDrawerEventRepository(session).create(
                cash_drawer_id=dto.id, event_type=event_type, message=message,
                occurred_at=datetime.now(UTC), opening_kind=opening_kind, user_id=user_id,
                username=username, cash_register_id=dto.cash_register_id,
                cash_register_name=cash_register_name, workstation=platform.node() or None,
                branch_location=None, sale_id=sale_id, invoice_id=invoice_id,
                debt_payment_id=debt_payment_id, reason=reason,
                response_time_ms=response_time_ms, port_used=params.port,
                ip_address_used=params.ip_address, ip_port_used=params.ip_port,
                model_snapshot=dto.model, brand_snapshot=dto.brand,
            )


def _validate_connection_params(
    connection_type: ConnectionType,
    port: str | None,
    ip_address: str | None,
    ip_port: int | None,
) -> str | None:
    if connection_type in _SERIAL_LIKE:
        if not port or not port.strip():
            raise BusinessRuleViolationError("El puerto es obligatorio para conexión USB/Serial.")
        return port.strip()
    if connection_type in _IP_LIKE:
        if not ip_address or not ip_address.strip() or not ip_port:
            raise BusinessRuleViolationError(
                "La dirección IP y el puerto son obligatorios para conexión Ethernet/Wi-Fi."
            )
    return port.strip() if port else None


def _validate_pulse_config(
    pulse_count: int, pulse_duration_ms: int, custom_command_hex: str | None
) -> None:
    """Falla temprano (al guardar la configuración) en vez de cuando se
    intente abrir el cajón por primera vez — reutiliza el mismo validador
    que ya usa el adaptador."""
    build_kick_command(
        pulse_count=pulse_count, pulse_duration_ms=pulse_duration_ms,
        custom_command_hex=custom_command_hex,
    )
