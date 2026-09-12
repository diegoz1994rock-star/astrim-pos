"""Modelos SQLAlchemy de cajones monederos configurados (Administración →
Dispositivos → Cajón monedero) y su historial de eventos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin
from pos.core.database.types import UTCDateTime
from pos.modules.cash_drawers.domain.enums import (
    CashDrawerEventType,
    CashDrawerOpeningKind,
    ConnectionStatus,
    ConnectionType,
    OpeningType,
)


class CashDrawer(Base, TimestampMixin):
    __tablename__ = "cash_drawers"
    __table_args__ = (
        UniqueConstraint("cash_register_id", name="uq_cash_drawers_cash_register_id"),
    )
    """La restricción única permite varias filas con `cash_register_id`
    `NULL` (cajones sin asignar) — cada valor NO nulo es único en SQL
    estándar, así que a lo sumo un cajón puede quedar asignado a una caja
    dada: "una caja solamente puede tener 1 cajón", nunca dos."""

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)

    opening_type: Mapped[OpeningType] = mapped_column(
        Enum(OpeningType, native_enum=False), default=OpeningType.DIRECT_SERIAL, nullable=False
    )
    linked_printer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    """Solo descriptivo, sin E/S — no existe módulo de impresoras fiscales
    propio todavía en el sistema."""

    connection_type: Mapped[ConnectionType] = mapped_column(
        Enum(ConnectionType, native_enum=False), default=ConnectionType.SERIAL, nullable=False
    )
    port: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baud_rate: Mapped[int | None] = mapped_column(Integer, default=9600, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    pulse_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pulse_duration_ms: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    custom_command_hex: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Si está presente, reemplaza por completo el comando ESC/POS estándar
    construido a partir de `pulse_count`/`pulse_duration_ms` — ver
    `domain/escpos_command.py::build_kick_command`."""

    cash_register_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_registers.id"), nullable=True
    )
    auto_open_after_sale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, native_enum=False),
        default=ConnectionStatus.DISCONNECTED,
        nullable=False,
    )
    last_successful_communication_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )


class CashDrawerEvent(Base):
    __tablename__ = "cash_drawer_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_drawer_id: Mapped[int] = mapped_column(
        ForeignKey("cash_drawers.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[CashDrawerEventType] = mapped_column(
        Enum(CashDrawerEventType, native_enum=False), nullable=False
    )
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    opening_kind: Mapped[CashDrawerOpeningKind | None] = mapped_column(
        Enum(CashDrawerOpeningKind, native_enum=False), nullable=True
    )
    """Solo aplica a eventos `OPENED`/`OPEN_FAILED` — `None` para
    conectar/desconectar/probar conexión."""
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cash_register_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cash_register_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    workstation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    """`platform.node()` — mismo patrón ya usado en
    `billing_service.py::register_payment` para el recibo de abono."""
    branch_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    """Proxy de "sucursal": no existe un concepto de sucursal propio en el
    sistema (POS de un solo local con varios puntos de caja) — se usa
    `CashRegisterDTO.location`, mismo criterio ya documentado para
    `InvoiceHistoryEntryDTO.branch_location`."""
    sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales.id", ondelete="SET NULL"), nullable=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    debt_payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("debt_payment_receipts.id", ondelete="SET NULL"), nullable=True
    )
    """`SET NULL` en las tres: el historial de aperturas es un registro de
    lo que pasó, no debe desaparecer si el registro relacionado se elimina
    (mismo criterio ya usado en `ScaleWeightRead.scale_device_id`)."""
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    """Motivo — obligatorio para apertura manual, ausente en aperturas
    automáticas (ya trazadas por `sale_id`/`debt_payment_id`)."""
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    port_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address_used: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_port_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
