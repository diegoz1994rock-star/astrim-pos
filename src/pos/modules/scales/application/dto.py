"""DTOs del módulo de básculas (Administración → Dispositivos → Báscula
electrónica)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pos.modules.scales.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    ScaleDeviceEventType,
    UnitOfMeasure,
    WeightReadingStatus,
)


@dataclass(frozen=True)
class ScaleDeviceConfigDTO:
    id: int
    name: str
    kind: str
    is_active: bool
    is_default: bool
    brand: str | None
    model: str | None
    serial_number: str | None
    description: str | None
    location: str | None
    cash_register_id: int | None
    station_label: str | None
    assigned_user_id: int | None
    connection_type: ConnectionType
    port: str | None
    baud_rate: int | None
    data_bits: int | None
    stop_bits: int | None
    parity: str | None
    ip_address: str | None
    ip_port: int | None
    bluetooth_address: str | None
    unit_of_measure: UnitOfMeasure
    decimal_places: int
    timeout_seconds: int
    read_frequency_seconds: int
    auto_read: bool
    stability_required: bool
    min_stable_seconds: Decimal
    auto_reconnect: bool
    current_tare: Decimal
    simulator_target_weight: Decimal | None
    connection_status: ConnectionStatus
    last_successful_communication_at: datetime | None


@dataclass(frozen=True)
class ScaleDeviceEventDTO:
    id: int
    event_type: ScaleDeviceEventType
    message: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class ScaleCapabilitiesDTO:
    """Capacidades del adaptador actualmente asignado al dispositivo (por
    `kind`) — se derivan en runtime del adaptador, nunca se persisten en
    BD, para no duplicar la fuente de verdad (ver `providers/registry.py`).
    `supports_tare` es la capacidad del adaptador de dar una tara remota de
    hardware, no si el botón "Tara" funciona: eso siempre funciona (tara
    universal por software, ver `ScaleReadService.apply_tare`)."""

    supports_tare: bool
    supports_calibration: bool


@dataclass(frozen=True)
class WeightReadingDTO:
    """Resultado de una lectura resuelta por `ScaleReadService.read` — el
    único tipo que consumen Ventas, el panel de pruebas y el diálogo de
    peso, sin que ninguno vuelva a hablar con un adaptador directamente."""

    device_id: int | None
    device_name: str | None
    gross_weight: Decimal
    net_weight: Decimal
    tare: Decimal
    unit: UnitOfMeasure
    status: WeightReadingStatus
    is_stable: bool
    duration_ms: int
    reconnected: bool
    read_at: datetime


@dataclass(frozen=True)
class ScaleDiagnosticsDTO:
    """Diagnóstico agregado, global o de un dispositivo puntual —
    equivalente de `BarcodeDiagnosticsDTO` para básculas."""

    connected: bool
    port: str | None
    baud_rate: int | None
    current_weight: Decimal | None
    last_weight: Decimal | None
    last_read_at: datetime | None
    last_error: str | None
    total_reads: int
    error_count: int
    reconnection_count: int
    average_read_duration_ms: float | None
    uptime_seconds: float | None


@dataclass(frozen=True)
class ScaleReadLogEntryDTO:
    id: int
    device_name: str | None
    product_name: str | None
    gross_weight: Decimal | None
    net_weight: Decimal | None
    unit: UnitOfMeasure
    status: WeightReadingStatus
    is_stable: bool
    username: str | None
    cash_register_name: str | None
    duration_ms: int | None
    error_message: str | None
    reconnected: bool
    occurred_at: datetime
