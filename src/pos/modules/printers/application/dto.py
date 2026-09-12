"""DTOs del módulo de Impresoras (Administración → Dispositivos →
Impresoras)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pos.modules.printers.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    Orientation,
    PrintDocumentType,
    PrinterEventType,
    PrinterType,
    PrintMethod,
)


@dataclass(frozen=True)
class PrinterDTO:
    id: int
    name: str
    alias: str | None
    is_active: bool
    is_default: bool
    brand: str | None
    model: str | None
    serial_number: str | None
    printer_type: PrinterType
    print_method: PrintMethod
    system_printer_name: str | None
    connection_type: ConnectionType
    port: str | None
    baud_rate: int | None
    ip_address: str | None
    ip_port: int | None
    timeout_seconds: int
    cash_register_id: int | None
    area: str | None
    copies: int
    orientation: Orientation
    margin_top_mm: Decimal
    margin_right_mm: Decimal
    margin_bottom_mm: Decimal
    margin_left_mm: Decimal
    resolution_dpi: int
    paper_width_mm: Decimal
    paper_length_mm: Decimal | None
    auto_cut: bool
    open_drawer_after_print: bool
    show_dialog: bool
    connection_status: ConnectionStatus
    last_successful_communication_at: datetime | None


@dataclass(frozen=True)
class PrinterEventDTO:
    id: int
    event_type: PrinterEventType
    message: str | None
    occurred_at: datetime
    user_id: int | None = None
    username: str | None = None
    cash_register_id: int | None = None
    cash_register_name: str | None = None
    document_type: PrintDocumentType | None = None
    document_reference: str | None = None
    sale_id: int | None = None
    invoice_id: int | None = None
    duration_ms: int | None = None
    printer_name_snapshot: str | None = None


@dataclass(frozen=True)
class PrinterDiagnosticsDTO:
    """Diagnóstico de una impresora puntual — mismo espíritu que
    `CashDrawerDiagnosticsDTO`/`ScaleDiagnosticsDTO`, agregando sobre su
    propio historial de eventos."""

    connected: bool
    available: bool
    online: bool | None
    """`None` cuando la vía de impresión no puede consultarlo (ver
    `PrinterProvider.query_paper_status`/limitaciones de `SYSTEM_DRIVER`)."""
    out_of_paper: bool | None
    port: str | None
    ip_address: str | None
    system_printer_name: str | None
    print_method: PrintMethod
    brand: str | None
    model: str | None
    average_response_time_ms: float | None
    last_print_at: datetime | None
    total_prints: int
    error_count: int
    last_error: str | None


@dataclass(frozen=True)
class DetectedPrinterDTO:
    """Resultado de "Buscar impresoras" — lo que el sistema operativo ya
    conoce, vía `QPrinterInfo`."""

    name: str
    make_and_model: str | None
    is_default: bool
    is_remote: bool
    location: str | None
    already_registered: bool
    """`True` si ya existe un `Printer` con `system_printer_name` igual a
    este nombre — evita registrarla dos veces desde el diálogo de
    detección."""
