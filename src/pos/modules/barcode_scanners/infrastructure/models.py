"""Modelos SQLAlchemy de lectores de códigos de barras configurados
(Administración → Dispositivos → Lectores de códigos de barras), su
historial de eventos de conexión/diagnóstico y su historial de lecturas."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin
from pos.core.database.types import UTCDateTime
from pos.modules.barcode_scanners.domain.enums import (
    BarcodeReadSource,
    BarcodeScannerEventType,
    BarcodeSymbology,
    CaseConversion,
    ConnectionStatus,
    ConnectionType,
    ScanResult,
)


class BarcodeScanner(Base, TimestampMixin):
    __tablename__ = "barcode_scanners"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    battery_level_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cash_register_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_registers.id"), nullable=True
    )

    connection_type: Mapped[ConnectionType] = mapped_column(
        Enum(ConnectionType, native_enum=False), default=ConnectionType.USB_HID, nullable=False
    )
    port: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baud_rate: Mapped[int | None] = mapped_column(Integer, default=9600, nullable=True)
    data_bits: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    stop_bits: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    parity: Mapped[str] = mapped_column(String(1), default="N", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bluetooth_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, native_enum=False),
        default=ConnectionStatus.DISCONNECTED,
        nullable=False,
    )
    last_read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_successful_communication_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )
    scan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connected_since: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    prefix: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    suffix: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    auto_enter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_tab: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validate_checksum: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    strip_special_chars: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    convert_case: Mapped[CaseConversion] = mapped_column(
        Enum(CaseConversion, native_enum=False), default=CaseConversion.NONE, nullable=False
    )
    ignore_spaces: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    inter_char_timeout_ms: Mapped[int] = mapped_column(Integer, default=50, nullable=False)


class BarcodeScannerEvent(Base):
    __tablename__ = "barcode_scanner_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    scanner_id: Mapped[int] = mapped_column(
        ForeignKey("barcode_scanners.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[BarcodeScannerEventType] = mapped_column(
        Enum(BarcodeScannerEventType, native_enum=False), nullable=False
    )
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class BarcodeScanHistoryEntry(Base):
    __tablename__ = "barcode_scan_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    scanner_id: Mapped[int] = mapped_column(
        ForeignKey("barcode_scanners.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(500), nullable=False)
    symbology: Mapped[BarcodeSymbology] = mapped_column(
        Enum(BarcodeSymbology, native_enum=False), nullable=False
    )
    cash_register_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_registers.id"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    result: Mapped[ScanResult] = mapped_column(Enum(ScanResult, native_enum=False), nullable=False)
    read_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class BarcodeRead(Base):
    """Registro centralizado de lecturas reales (Ventas, "Probar lector",
    formulario de producto) — independiente del inventario de dispositivos
    de arriba: no requiere que exista ningún `BarcodeScanner` registrado,
    ver `BarcodeReadService`."""

    __tablename__ = "barcode_reads"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    symbology: Mapped[BarcodeSymbology] = mapped_column(
        Enum(BarcodeSymbology, native_enum=False), nullable=False
    )
    found: Mapped[bool] = mapped_column(Boolean, nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    source: Mapped[BarcodeReadSource] = mapped_column(
        Enum(BarcodeReadSource, native_enum=False), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cash_register_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cash_register_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
