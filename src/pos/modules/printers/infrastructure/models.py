"""Modelos SQLAlchemy de impresoras configuradas (Administración →
Dispositivos → Impresoras) y su historial de auditoría de impresiones."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin
from pos.core.database.types import UTCDateTime
from pos.modules.printers.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    Orientation,
    PrintDocumentType,
    PrinterEventType,
    PrinterType,
    PrintMethod,
)


class Printer(Base, TimestampMixin):
    """Impresora configurada. `print_method` decide qué adaptador
    (`application/providers/registry.py`) la maneja — `SYSTEM_DRIVER` usa
    `system_printer_name` (nombre tal cual lo expone el SO); `RAW_ESCPOS`
    usa puerto/IP como báscula/cajón. Sin restricción de unicidad en
    `cash_register_id`: una caja puede tener más de una impresora
    (recibos + etiquetas, por ejemplo) — a diferencia del cajón monedero,
    nada en el pedido exige una sola impresora por caja."""

    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    alias: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    printer_type: Mapped[PrinterType] = mapped_column(
        Enum(PrinterType, native_enum=False), default=PrinterType.RECEIPT, nullable=False
    )

    print_method: Mapped[PrintMethod] = mapped_column(
        Enum(PrintMethod, native_enum=False), default=PrintMethod.SYSTEM_DRIVER, nullable=False
    )
    system_printer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Nombre exacto tal cual lo expone `QPrinterInfo` — solo aplica
    cuando `print_method` es `SYSTEM_DRIVER`."""

    connection_type: Mapped[ConnectionType] = mapped_column(
        Enum(ConnectionType, native_enum=False), default=ConnectionType.USB, nullable=False
    )
    port: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baud_rate: Mapped[int | None] = mapped_column(Integer, default=9600, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    """Solo aplican cuando `print_method` es `RAW_ESCPOS`."""

    cash_register_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_registers.id"), nullable=True
    )
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """Texto libre (ej. "Cocina", "Despacho", "Administración") — no se
    reutiliza el catálogo `job_areas` (RRHH/permisos, concepto distinto de
    "dónde está físicamente este dispositivo"), mismo criterio ya usado
    para `station_label`/`location` en los módulos hermanos."""

    copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    orientation: Mapped[Orientation] = mapped_column(
        Enum(Orientation, native_enum=False), default=Orientation.PORTRAIT, nullable=False
    )
    margin_top_mm: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=5, nullable=False)
    margin_right_mm: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=5, nullable=False)
    margin_bottom_mm: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=5, nullable=False)
    margin_left_mm: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=5, nullable=False)
    resolution_dpi: Mapped[int] = mapped_column(Integer, default=203, nullable=False)
    paper_width_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=80, nullable=False)
    paper_length_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    """`None` = papel en rollo continuo (típico de térmicas)."""
    auto_cut: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    open_drawer_after_print: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_dialog: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """Solo aplica a `SYSTEM_DRIVER`: si es `True`, muestra el diálogo de
    impresión nativo del SO en vez de imprimir directo/silencioso."""

    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, native_enum=False),
        default=ConnectionStatus.DISCONNECTED,
        nullable=False,
    )
    last_successful_communication_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )


class PrinterEvent(Base):
    """Historial de auditoría de una impresora — conexiones/errores y,
    sobre todo, cada trabajo de impresión real (factura/recibo/página de
    prueba) con su contexto completo. `SET NULL` (no cascada): es un
    registro de negocio, no debe desaparecer si la impresora se elimina
    de la configuración, mismo criterio que `CashDrawerEvent`."""

    __tablename__ = "printer_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[PrinterEventType] = mapped_column(
        Enum(PrinterEventType, native_enum=False), nullable=False
    )
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)

    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cash_register_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cash_register_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    document_type: Mapped[PrintDocumentType | None] = mapped_column(
        Enum(PrintDocumentType, native_enum=False), nullable=True
    )
    document_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """Número de factura/recibo (ej. `F-000001`) — texto libre para no
    acoplar este módulo a la numeración de `billing`."""
    sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales.id", ondelete="SET NULL"), nullable=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    printer_name_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
