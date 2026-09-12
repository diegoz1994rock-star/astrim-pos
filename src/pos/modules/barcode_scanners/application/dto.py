"""DTOs del módulo de Lectores de códigos de barras."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.barcode_scanners.domain.enums import (
    BarcodeReadSource,
    BarcodeSymbology,
    CaseConversion,
    ConnectionStatus,
    ConnectionType,
    ScanResult,
)
from pos.modules.barcode_scanners.domain.scan_parsing import ParsedScan
from pos.modules.products.application.dto import ProductDTO


@dataclass(frozen=True)
class BarcodeScannerDTO:
    id: int
    name: str
    kind: str
    is_active: bool
    is_default: bool
    brand: str | None
    model: str | None
    serial_number: str | None
    description: str | None
    firmware_version: str | None
    battery_level_percent: int | None
    cash_register_id: int | None

    connection_type: ConnectionType
    port: str | None
    baud_rate: int | None
    data_bits: int
    stop_bits: float
    parity: str
    ip_address: str | None
    ip_port: int | None
    bluetooth_address: str | None

    connection_status: ConnectionStatus
    last_read_at: datetime | None
    last_successful_communication_at: datetime | None
    scan_count: int
    connected_since: datetime | None

    prefix: str
    suffix: str
    auto_enter: bool
    auto_tab: bool
    min_length: int | None
    max_length: int | None
    validate_checksum: bool
    strip_special_chars: bool
    convert_case: CaseConversion
    ignore_spaces: bool
    inter_char_timeout_ms: int


@dataclass(frozen=True)
class BarcodeScannerEventDTO:
    id: int
    event_type: str
    message: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class ScanHistoryEntryDTO:
    id: int
    scanner_id: int
    code: str
    symbology: BarcodeSymbology
    cash_register_id: int | None
    user_id: int | None
    result: ScanResult
    read_duration_ms: int | None
    is_simulated: bool
    occurred_at: datetime


@dataclass(frozen=True)
class ScanOutcomeDTO:
    """Resultado completo de una lectura (real, por HID, o simulada) — lo
    que necesita el panel de pruebas para mostrar de inmediato Código
    leído/Tipo/Caracteres/Hora/Tiempo de lectura."""

    parsed: ParsedScan
    duration_ms: int
    is_simulated: bool
    occurred_at: datetime


@dataclass(frozen=True)
class BarcodeSettingsDTO:
    """Configuración global del lector — Administración → Dispositivos →
    Código de barras. Persistida vía `BusinessSettingsService`, no requiere
    tabla propia."""

    reader_enabled: bool
    auto_enter_enabled: bool
    duplicate_debounce_ms: int
    sound_on_success: bool
    sound_on_not_found: bool
    show_visual_notification: bool


@dataclass(frozen=True)
class BarcodeReadResultDTO:
    """Resultado de `BarcodeReadService.resolve_scan` — la vista decide
    qué hacer (agregar al carrito, limpiar/reenfocar el campo, sonido/
    aviso) a partir de esto, sin repetir la lógica de búsqueda."""

    code: str
    symbology: BarcodeSymbology
    found: bool
    product: ProductDTO | None
    ignored: bool
    """`True` si la lectura no se procesó (lector desactivado o rebote de
    doble lectura dentro del intervalo configurado) — ver `reason`."""
    reason: str | None


@dataclass(frozen=True)
class BarcodeReadLogEntryDTO:
    id: int
    code: str
    symbology: BarcodeSymbology
    found: bool
    product_id: int | None
    product_name: str | None
    source: BarcodeReadSource
    username: str | None
    cash_register_name: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class BarcodeDiagnosticsDTO:
    last_code: str | None
    last_read_at: datetime | None
    total_reads: int
    error_count: int
    average_interval_ms: float | None
    """Tiempo promedio entre lecturas consecutivas, en milisegundos —
    `None` si hay menos de 2 lecturas registradas."""
    has_recent_activity: bool
    """`True` si hubo al menos una lectura en los últimos 5 minutos — la
    única señal honesta de "lector activo" que el software puede dar para
    HID (no hay forma de "detectar" el dispositivo en sí, ver
    `HidWedgeDriver`)."""
