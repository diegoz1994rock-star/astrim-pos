"""Casos de uso de administración de lectores de códigos de barras: CRUD,
conexión/prueba/lectura real vía el driver correspondiente, e historial de
lecturas — una lectura real y una simulada ("Simular lectura") pasan por
exactamente el mismo camino de procesamiento (`_process_scan`)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.barcode_scanners.application.dto import (
    BarcodeScannerDTO,
    BarcodeScannerEventDTO,
    ScanHistoryEntryDTO,
    ScanOutcomeDTO,
)
from pos.modules.barcode_scanners.application.providers.base import ScannerConnectionParams
from pos.modules.barcode_scanners.application.providers.registry import get_scanner_driver
from pos.modules.barcode_scanners.domain.enums import (
    BarcodeScannerEventType,
    CaseConversion,
    ConnectionStatus,
    ConnectionType,
    ScanResult,
)
from pos.modules.barcode_scanners.domain.scan_parsing import ScanConfig, apply_scan_config
from pos.modules.barcode_scanners.infrastructure.models import BarcodeScanner, BarcodeScannerEvent
from pos.modules.barcode_scanners.infrastructure.repository import (
    BarcodeScanHistoryRepository,
    BarcodeScannerEventRepository,
    BarcodeScannerRepository,
)

_SERIAL_LIKE = (ConnectionType.USB_SERIAL, ConnectionType.BLUETOOTH_SERIAL, ConnectionType.RS232)
_IP_LIKE = (ConnectionType.TCP_IP, ConnectionType.WIFI)
_HID_LIKE = (ConnectionType.USB_HID, ConnectionType.BLUETOOTH_HID)


def _to_dto(scanner: BarcodeScanner) -> BarcodeScannerDTO:
    return BarcodeScannerDTO(
        id=scanner.id, name=scanner.name, kind=scanner.kind, is_active=scanner.is_active,
        is_default=scanner.is_default, brand=scanner.brand, model=scanner.model,
        serial_number=scanner.serial_number, description=scanner.description,
        firmware_version=scanner.firmware_version,
        battery_level_percent=scanner.battery_level_percent,
        cash_register_id=scanner.cash_register_id,
        connection_type=scanner.connection_type, port=scanner.port, baud_rate=scanner.baud_rate,
        data_bits=scanner.data_bits, stop_bits=scanner.stop_bits, parity=scanner.parity,
        ip_address=scanner.ip_address, ip_port=scanner.ip_port,
        bluetooth_address=scanner.bluetooth_address,
        connection_status=scanner.connection_status, last_read_at=scanner.last_read_at,
        last_successful_communication_at=scanner.last_successful_communication_at,
        scan_count=scanner.scan_count, connected_since=scanner.connected_since,
        prefix=scanner.prefix, suffix=scanner.suffix, auto_enter=scanner.auto_enter,
        auto_tab=scanner.auto_tab, min_length=scanner.min_length, max_length=scanner.max_length,
        validate_checksum=scanner.validate_checksum,
        strip_special_chars=scanner.strip_special_chars,
        convert_case=scanner.convert_case, ignore_spaces=scanner.ignore_spaces,
        inter_char_timeout_ms=scanner.inter_char_timeout_ms,
    )


def _event_to_dto(event: BarcodeScannerEvent) -> BarcodeScannerEventDTO:
    return BarcodeScannerEventDTO(
        id=event.id, event_type=event.event_type.value, message=event.message,
        occurred_at=event.occurred_at,
    )


def _params(scanner: BarcodeScannerDTO) -> ScannerConnectionParams:
    return ScannerConnectionParams(
        connection_type=scanner.connection_type, port=scanner.port, baud_rate=scanner.baud_rate,
        data_bits=scanner.data_bits, stop_bits=scanner.stop_bits, parity=scanner.parity,
        ip_address=scanner.ip_address, ip_port=scanner.ip_port,
        bluetooth_address=scanner.bluetooth_address,
    )


def _scan_config(scanner: BarcodeScannerDTO) -> ScanConfig:
    return ScanConfig(
        prefix=scanner.prefix, suffix=scanner.suffix, auto_enter=scanner.auto_enter,
        auto_tab=scanner.auto_tab, min_length=scanner.min_length, max_length=scanner.max_length,
        validate_checksum=scanner.validate_checksum,
        strip_special_chars=scanner.strip_special_chars,
        convert_case=scanner.convert_case, ignore_spaces=scanner.ignore_spaces,
        inter_char_timeout_ms=scanner.inter_char_timeout_ms,
    )


class BarcodeScannerService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_devices(self) -> list[BarcodeScannerDTO]:
        with session_scope() as session:
            return [_to_dto(s) for s in BarcodeScannerRepository(session).list_all()]

    def create_device(
        self,
        *,
        name: str,
        kind: str = "generic",
        brand: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        description: str | None = None,
        cash_register_id: int | None = None,
        connection_type: ConnectionType = ConnectionType.USB_HID,
        port: str | None = None,
        baud_rate: int | None = 9600,
        data_bits: int = 8,
        stop_bits: float = 1,
        parity: str = "N",
        ip_address: str | None = None,
        ip_port: int | None = None,
        bluetooth_address: str | None = None,
        prefix: str = "",
        suffix: str = "",
        auto_enter: bool = False,
        auto_tab: bool = False,
        min_length: int | None = None,
        max_length: int | None = None,
        validate_checksum: bool = False,
        strip_special_chars: bool = False,
        convert_case: CaseConversion = CaseConversion.NONE,
        ignore_spaces: bool = False,
        inter_char_timeout_ms: int = 50,
    ) -> BarcodeScannerDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del lector es obligatorio.")
        port = _validate_connection_params(connection_type, port, ip_address, ip_port)
        with session_scope() as session:
            repo = BarcodeScannerRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe un lector llamado '{name}'.")
            scanner = repo.create(
                name=name, kind=kind, brand=brand, model=model, serial_number=serial_number,
                description=description, cash_register_id=cash_register_id,
                connection_type=connection_type, port=port, baud_rate=baud_rate,
                data_bits=data_bits, stop_bits=stop_bits, parity=parity,
                ip_address=ip_address, ip_port=ip_port, bluetooth_address=bluetooth_address,
                prefix=prefix, suffix=suffix, auto_enter=auto_enter, auto_tab=auto_tab,
                min_length=min_length, max_length=max_length, validate_checksum=validate_checksum,
                strip_special_chars=strip_special_chars, convert_case=convert_case,
                ignore_spaces=ignore_spaces, inter_char_timeout_ms=inter_char_timeout_ms,
            )
            return _to_dto(scanner)

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
        cash_register_id: int | None = None,
        connection_type: ConnectionType = ConnectionType.USB_HID,
        port: str | None = None,
        baud_rate: int | None = 9600,
        data_bits: int = 8,
        stop_bits: float = 1,
        parity: str = "N",
        ip_address: str | None = None,
        ip_port: int | None = None,
        bluetooth_address: str | None = None,
        prefix: str = "",
        suffix: str = "",
        auto_enter: bool = False,
        auto_tab: bool = False,
        min_length: int | None = None,
        max_length: int | None = None,
        validate_checksum: bool = False,
        strip_special_chars: bool = False,
        convert_case: CaseConversion = CaseConversion.NONE,
        ignore_spaces: bool = False,
        inter_char_timeout_ms: int = 50,
    ) -> BarcodeScannerDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del lector es obligatorio.")
        port = _validate_connection_params(connection_type, port, ip_address, ip_port)
        with session_scope() as session:
            repo = BarcodeScannerRepository(session)
            scanner = repo.get(device_id)
            if scanner is None:
                raise NotFoundError(f"No existe el lector con id={device_id}.")
            existing = repo.get_by_name(name)
            if existing is not None and existing.id != device_id:
                raise ConflictError(f"Ya existe un lector llamado '{name}'.")
            repo.update(
                scanner, name=name, kind=kind, brand=brand, model=model,
                serial_number=serial_number, description=description,
                cash_register_id=cash_register_id, connection_type=connection_type,
                port=port, baud_rate=baud_rate, data_bits=data_bits, stop_bits=stop_bits,
                parity=parity, ip_address=ip_address, ip_port=ip_port,
                bluetooth_address=bluetooth_address, prefix=prefix, suffix=suffix,
                auto_enter=auto_enter, auto_tab=auto_tab, min_length=min_length,
                max_length=max_length, validate_checksum=validate_checksum,
                strip_special_chars=strip_special_chars, convert_case=convert_case,
                ignore_spaces=ignore_spaces, inter_char_timeout_ms=inter_char_timeout_ms,
            )
            return _to_dto(scanner)

    def set_device_active(self, device_id: int, is_active: bool) -> BarcodeScannerDTO:
        with session_scope() as session:
            repo = BarcodeScannerRepository(session)
            scanner = repo.get(device_id)
            if scanner is None:
                raise NotFoundError(f"No existe el lector con id={device_id}.")
            repo.set_active(scanner, is_active)
            return _to_dto(scanner)

    def set_default_device(self, device_id: int) -> BarcodeScannerDTO:
        with session_scope() as session:
            repo = BarcodeScannerRepository(session)
            scanner = repo.get(device_id)
            if scanner is None:
                raise NotFoundError(f"No existe el lector con id={device_id}.")
            repo.set_default(scanner)
            return _to_dto(scanner)

    def delete_device(self, device_id: int) -> None:
        with session_scope() as session:
            repo = BarcodeScannerRepository(session)
            scanner = repo.get(device_id)
            if scanner is None:
                raise NotFoundError(f"No existe el lector con id={device_id}.")
            repo.delete(scanner)

    def test_connection(self, device_id: int) -> bool:
        dto = self._get_dto(device_id)
        try:
            result = get_scanner_driver(dto.connection_type, dto.kind).test_connection(_params(dto))
        except BusinessRuleViolationError as error:
            self._log_event(device_id, BarcodeScannerEventType.TEST_CONNECTION_FAILED, str(error))
            raise
        self._log_event(device_id, BarcodeScannerEventType.TEST_CONNECTION_OK, None)
        return result

    def connect(self, device_id: int) -> BarcodeScannerDTO:
        dto = self._get_dto(device_id)
        try:
            get_scanner_driver(dto.connection_type, dto.kind).test_connection(_params(dto))
        except BusinessRuleViolationError as error:
            self._set_status(device_id, ConnectionStatus.ERROR)
            self._log_event(device_id, BarcodeScannerEventType.ERROR, str(error))
            raise
        self._set_status(device_id, ConnectionStatus.CONNECTED)
        self._log_event(device_id, BarcodeScannerEventType.CONNECTED, None)
        return self._get_dto(device_id)

    def disconnect(self, device_id: int) -> BarcodeScannerDTO:
        self._set_status(device_id, ConnectionStatus.DISCONNECTED)
        self._log_event(device_id, BarcodeScannerEventType.DISCONNECTED, None)
        return self._get_dto(device_id)

    def read_code(self, device_id: int) -> ScanOutcomeDTO:
        dto = self._get_dto(device_id)
        start = time.perf_counter()
        try:
            raw = get_scanner_driver(dto.connection_type, dto.kind).read_code(_params(dto))
        except BusinessRuleViolationError as error:
            self._log_event(device_id, BarcodeScannerEventType.READ_FAILED, str(error))
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        return self._process_scan(device_id, raw, duration_ms=duration_ms, is_simulated=False)

    def simulate_scan(self, device_id: int, raw_code: str) -> ScanOutcomeDTO:
        return self._process_scan(device_id, raw_code, duration_ms=0, is_simulated=True)

    def process_hid_scan(self, device_id: int, raw_code: str, duration_ms: int) -> ScanOutcomeDTO:
        """Procesa una lectura real llegada por HID (el panel de pruebas la
        recibe como texto tecleado en un campo con foco, no a través del
        driver — ver `HidWedgeDriver`)."""
        return self._process_scan(device_id, raw_code, duration_ms=duration_ms, is_simulated=False)

    def list_events(self, device_id: int, limit: int = 50) -> list[BarcodeScannerEventDTO]:
        with session_scope() as session:
            events = BarcodeScannerEventRepository(session).list_for_device(device_id, limit)
            return [_event_to_dto(e) for e in events]

    def list_scan_history(self, device_id: int, limit: int = 100) -> list[ScanHistoryEntryDTO]:
        with session_scope() as session:
            entries = BarcodeScanHistoryRepository(session).list_for_device(device_id, limit)
            return [
                ScanHistoryEntryDTO(
                    id=e.id, scanner_id=e.scanner_id, code=e.code, symbology=e.symbology,
                    cash_register_id=e.cash_register_id, user_id=e.user_id, result=e.result,
                    read_duration_ms=e.read_duration_ms, is_simulated=e.is_simulated,
                    occurred_at=e.occurred_at,
                )
                for e in entries
            ]

    def reset_stale_connections(self) -> None:
        with session_scope() as session:
            BarcodeScannerRepository(session).reset_all_connection_statuses()

    # -- internos -------------------------------------------------------

    def _process_scan(
        self, device_id: int, raw_code: str, *, duration_ms: int, is_simulated: bool
    ) -> ScanOutcomeDTO:
        dto = self._get_dto(device_id)
        parsed = apply_scan_config(raw_code, _scan_config(dto))
        now = datetime.now(UTC)
        with session_scope() as session:
            repo = BarcodeScannerRepository(session)
            scanner = repo.get(device_id)
            if scanner is not None:
                repo.record_scan(scanner, occurred_at=now)
            BarcodeScanHistoryRepository(session).create(
                scanner_id=device_id, code=parsed.code, symbology=parsed.symbology,
                cash_register_id=dto.cash_register_id, user_id=None,
                result=ScanResult.SUCCESS if parsed.is_valid else ScanResult.FAILED,
                read_duration_ms=duration_ms, is_simulated=is_simulated, occurred_at=now,
            )
        event_type = (
            BarcodeScannerEventType.READ_SUCCESS if parsed.is_valid
            else BarcodeScannerEventType.READ_FAILED
        )
        detail = parsed.code if parsed.is_valid else "; ".join(parsed.errors)
        self._log_event(device_id, event_type, detail)
        return ScanOutcomeDTO(
            parsed=parsed, duration_ms=duration_ms, is_simulated=is_simulated, occurred_at=now
        )

    def _get_dto(self, device_id: int) -> BarcodeScannerDTO:
        with session_scope() as session:
            scanner = BarcodeScannerRepository(session).get(device_id)
            if scanner is None:
                raise NotFoundError(f"No existe el lector con id={device_id}.")
            return _to_dto(scanner)

    def _set_status(self, device_id: int, status: ConnectionStatus) -> None:
        with session_scope() as session:
            repo = BarcodeScannerRepository(session)
            scanner = repo.get(device_id)
            if scanner is None:
                raise NotFoundError(f"No existe el lector con id={device_id}.")
            repo.set_connection_status(scanner, status, occurred_at=datetime.now(UTC))

    def _log_event(
        self, device_id: int, event_type: BarcodeScannerEventType, message: str | None
    ) -> None:
        with session_scope() as session:
            BarcodeScannerEventRepository(session).create(
                scanner_id=device_id, event_type=event_type, message=message,
                occurred_at=datetime.now(UTC),
            )


def _validate_connection_params(
    connection_type: ConnectionType,
    port: str | None,
    ip_address: str | None,
    ip_port: int | None,
) -> str | None:
    if connection_type in _HID_LIKE:
        return None
    if connection_type in _SERIAL_LIKE:
        if not port or not port.strip():
            raise BusinessRuleViolationError("El puerto es obligatorio para este tipo de conexión.")
        return port.strip()
    if connection_type in _IP_LIKE and (not ip_address or not ip_address.strip() or not ip_port):
        raise BusinessRuleViolationError(
            "La dirección IP y el puerto son obligatorios para conexión TCP/IP o Wi-Fi."
        )
    return port.strip() if port else None
