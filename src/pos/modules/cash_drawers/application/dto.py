"""DTOs del módulo de Cajón monedero (Gaveta de efectivo)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.cash_drawers.domain.enums import (
    CashDrawerEventType,
    CashDrawerOpeningKind,
    ConnectionStatus,
    ConnectionType,
    OpeningType,
)


@dataclass(frozen=True)
class CashDrawerDTO:
    id: int
    name: str
    kind: str
    is_active: bool
    is_default: bool
    brand: str | None
    model: str | None
    serial_number: str | None
    location: str | None
    opening_type: OpeningType
    linked_printer_name: str | None
    connection_type: ConnectionType
    port: str | None
    baud_rate: int | None
    ip_address: str | None
    ip_port: int | None
    timeout_seconds: int
    pulse_count: int
    pulse_duration_ms: int
    custom_command_hex: str | None
    cash_register_id: int | None
    auto_open_after_sale: bool
    connection_status: ConnectionStatus
    last_successful_communication_at: datetime | None


@dataclass(frozen=True)
class CashDrawerEventDTO:
    id: int
    event_type: CashDrawerEventType
    message: str | None
    occurred_at: datetime
    opening_kind: CashDrawerOpeningKind | None = None
    user_id: int | None = None
    username: str | None = None
    cash_register_id: int | None = None
    cash_register_name: str | None = None
    workstation: str | None = None
    branch_location: str | None = None
    sale_id: int | None = None
    invoice_id: int | None = None
    debt_payment_id: int | None = None
    reason: str | None = None
    response_time_ms: int | None = None
    port_used: str | None = None
    ip_address_used: str | None = None
    ip_port_used: int | None = None
    model_snapshot: str | None = None
    brand_snapshot: str | None = None


@dataclass(frozen=True)
class CashDrawerDiagnosticsDTO:
    """Diagnóstico de un cajón puntual — mismo espíritu que
    `ScaleDiagnosticsDTO`/`BarcodeDiagnosticsDTO`, agregando sobre su
    propio historial de eventos."""

    connected: bool
    port: str | None
    ip_address: str | None
    ip_port: int | None
    kind: str
    brand: str | None
    model: str | None
    last_opened_at: datetime | None
    average_response_time_ms: float | None
    total_opens: int
    error_count: int
    last_error: str | None
