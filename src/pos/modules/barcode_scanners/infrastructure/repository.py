"""Acceso a datos de lectores de códigos de barras, su historial de eventos
de conexión/diagnóstico y su historial de lecturas."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pos.modules.barcode_scanners.domain.enums import (
    BarcodeScannerEventType,
    BarcodeSymbology,
    CaseConversion,
    ConnectionStatus,
    ConnectionType,
    ScanResult,
)
from pos.modules.barcode_scanners.infrastructure.models import (
    BarcodeScanHistoryEntry,
    BarcodeScanner,
    BarcodeScannerEvent,
)


class BarcodeScannerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[BarcodeScanner]:
        return list(self._session.scalars(select(BarcodeScanner).order_by(BarcodeScanner.name)))

    def get(self, scanner_id: int) -> BarcodeScanner | None:
        return self._session.get(BarcodeScanner, scanner_id)

    def get_by_name(self, name: str) -> BarcodeScanner | None:
        return self._session.scalar(select(BarcodeScanner).where(BarcodeScanner.name == name))

    def get_default(self) -> BarcodeScanner | None:
        return self._session.scalar(
            select(BarcodeScanner).where(BarcodeScanner.is_default.is_(True))
        )

    def create(
        self,
        *,
        name: str,
        kind: str,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        description: str | None,
        cash_register_id: int | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        data_bits: int,
        stop_bits: float,
        parity: str,
        ip_address: str | None,
        ip_port: int | None,
        bluetooth_address: str | None,
        prefix: str,
        suffix: str,
        auto_enter: bool,
        auto_tab: bool,
        min_length: int | None,
        max_length: int | None,
        validate_checksum: bool,
        strip_special_chars: bool,
        convert_case: CaseConversion,
        ignore_spaces: bool,
        inter_char_timeout_ms: int,
    ) -> BarcodeScanner:
        scanner = BarcodeScanner(
            name=name, kind=kind, is_active=True, is_default=False,
            brand=brand, model=model, serial_number=serial_number, description=description,
            cash_register_id=cash_register_id,
            connection_type=connection_type, port=port, baud_rate=baud_rate,
            data_bits=data_bits, stop_bits=stop_bits, parity=parity,
            ip_address=ip_address, ip_port=ip_port, bluetooth_address=bluetooth_address,
            prefix=prefix, suffix=suffix, auto_enter=auto_enter, auto_tab=auto_tab,
            min_length=min_length, max_length=max_length, validate_checksum=validate_checksum,
            strip_special_chars=strip_special_chars, convert_case=convert_case,
            ignore_spaces=ignore_spaces, inter_char_timeout_ms=inter_char_timeout_ms,
        )
        self._session.add(scanner)
        self._session.flush()
        return scanner

    def update(
        self,
        scanner: BarcodeScanner,
        *,
        name: str,
        kind: str,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        description: str | None,
        cash_register_id: int | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        data_bits: int,
        stop_bits: float,
        parity: str,
        ip_address: str | None,
        ip_port: int | None,
        bluetooth_address: str | None,
        prefix: str,
        suffix: str,
        auto_enter: bool,
        auto_tab: bool,
        min_length: int | None,
        max_length: int | None,
        validate_checksum: bool,
        strip_special_chars: bool,
        convert_case: CaseConversion,
        ignore_spaces: bool,
        inter_char_timeout_ms: int,
    ) -> None:
        scanner.name = name
        scanner.kind = kind
        scanner.brand = brand
        scanner.model = model
        scanner.serial_number = serial_number
        scanner.description = description
        scanner.cash_register_id = cash_register_id
        scanner.connection_type = connection_type
        scanner.port = port
        scanner.baud_rate = baud_rate
        scanner.data_bits = data_bits
        scanner.stop_bits = stop_bits
        scanner.parity = parity
        scanner.ip_address = ip_address
        scanner.ip_port = ip_port
        scanner.bluetooth_address = bluetooth_address
        scanner.prefix = prefix
        scanner.suffix = suffix
        scanner.auto_enter = auto_enter
        scanner.auto_tab = auto_tab
        scanner.min_length = min_length
        scanner.max_length = max_length
        scanner.validate_checksum = validate_checksum
        scanner.strip_special_chars = strip_special_chars
        scanner.convert_case = convert_case
        scanner.ignore_spaces = ignore_spaces
        scanner.inter_char_timeout_ms = inter_char_timeout_ms
        self._session.flush()

    def set_active(self, scanner: BarcodeScanner, is_active: bool) -> None:
        scanner.is_active = is_active

    def set_default(self, scanner: BarcodeScanner) -> None:
        self._session.execute(update(BarcodeScanner).values(is_default=False))
        scanner.is_default = True
        self._session.flush()

    def set_connection_status(
        self, scanner: BarcodeScanner, status: ConnectionStatus, *, occurred_at: datetime
    ) -> None:
        scanner.connection_status = status
        if status is ConnectionStatus.CONNECTED:
            scanner.last_successful_communication_at = occurred_at
            scanner.connected_since = occurred_at
        else:
            scanner.connected_since = None

    def record_scan(self, scanner: BarcodeScanner, *, occurred_at: datetime) -> None:
        scanner.last_read_at = occurred_at
        scanner.last_successful_communication_at = occurred_at
        scanner.scan_count += 1

    def reset_all_connection_statuses(self) -> None:
        self._session.execute(
            update(BarcodeScanner).values(
                connection_status=ConnectionStatus.DISCONNECTED, connected_since=None
            )
        )

    def delete(self, scanner: BarcodeScanner) -> None:
        self._session.delete(scanner)


class BarcodeScannerEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_device(self, scanner_id: int, limit: int = 50) -> list[BarcodeScannerEvent]:
        return list(
            self._session.scalars(
                select(BarcodeScannerEvent)
                .where(BarcodeScannerEvent.scanner_id == scanner_id)
                .order_by(BarcodeScannerEvent.occurred_at.desc())
                .limit(limit)
            )
        )

    def create(
        self,
        *,
        scanner_id: int,
        event_type: BarcodeScannerEventType,
        message: str | None,
        occurred_at: datetime,
    ) -> BarcodeScannerEvent:
        event = BarcodeScannerEvent(
            scanner_id=scanner_id, event_type=event_type, message=message, occurred_at=occurred_at,
        )
        self._session.add(event)
        self._session.flush()
        return event


class BarcodeScanHistoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_device(self, scanner_id: int, limit: int = 100) -> list[BarcodeScanHistoryEntry]:
        return list(
            self._session.scalars(
                select(BarcodeScanHistoryEntry)
                .where(BarcodeScanHistoryEntry.scanner_id == scanner_id)
                .order_by(BarcodeScanHistoryEntry.occurred_at.desc())
                .limit(limit)
            )
        )

    def create(
        self,
        *,
        scanner_id: int,
        code: str,
        symbology: BarcodeSymbology,
        cash_register_id: int | None,
        user_id: int | None,
        result: ScanResult,
        read_duration_ms: int | None,
        is_simulated: bool,
        occurred_at: datetime,
    ) -> BarcodeScanHistoryEntry:
        entry = BarcodeScanHistoryEntry(
            scanner_id=scanner_id, code=code, symbology=symbology,
            cash_register_id=cash_register_id, user_id=user_id, result=result,
            read_duration_ms=read_duration_ms, is_simulated=is_simulated, occurred_at=occurred_at,
        )
        self._session.add(entry)
        self._session.flush()
        return entry
