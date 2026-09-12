"""Modelos SQLAlchemy de básculas configuradas (Administración →
Dispositivos → Báscula electrónica) y su historial de eventos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin
from pos.core.database.types import UTCDateTime
from pos.modules.scales.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    ScaleDeviceEventType,
    UnitOfMeasure,
    WeightReadingStatus,
)


class ScaleDeviceConfig(Base, TimestampMixin):
    """Báscula configurada. `kind` identifica qué adaptador
    (`application/providers/registry.py`) debe conectarse y leer el peso —
    agregar una marca nueva a futuro solo requiere un adaptador nuevo
    registrado con una nueva clave de `kind`, sin tocar este modelo."""

    __tablename__ = "scale_device_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cash_register_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_registers.id"), nullable=True
    )
    station_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """Estación/PC de mostrador donde está instalada — texto libre, sin FK
    a `sync_stations` a propósito: no todo negocio usa sincronización
    multi-estación, y este módulo no debe depender de ese módulo."""
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    connection_type: Mapped[ConnectionType] = mapped_column(
        Enum(ConnectionType, native_enum=False), default=ConnectionType.SERIAL, nullable=False
    )
    port: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baud_rate: Mapped[int | None] = mapped_column(Integer, default=9600, nullable=True)
    data_bits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_bits: Mapped[float | None] = mapped_column(Float, nullable=True)
    """`Float` (no `Integer`) para poder representar 1.5 bits de parada —
    misma columna que `BarcodeScanner.stop_bits`."""
    parity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    """Aplican solo cuando `connection_type` es `USB`/`SERIAL`."""
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Aplican solo cuando `connection_type` es `ETHERNET`/`WIFI`."""
    bluetooth_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    unit_of_measure: Mapped[UnitOfMeasure] = mapped_column(
        Enum(UnitOfMeasure, native_enum=False), default=UnitOfMeasure.KG, nullable=False
    )
    decimal_places: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    read_frequency_seconds: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    auto_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    stability_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    """Si `False`, `ScaleReadService.read` devuelve `is_stable=True` en la
    primera lectura válida — algunas básculas económicas no valen la pena
    esperar (o el negocio prefiere velocidad a exactitud)."""
    min_stable_seconds: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.50"), nullable=False
    )
    auto_reconnect: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    """Si una lectura falla por error de conexión, `ScaleReadService`
    reintenta conectar una vez antes de propagar el error — no hay conexión
    persistente que vigilar (el adaptador abre/cierra el puerto por
    operación), así que "reconectar" es honestamente "reintentar en el
    siguiente intento de lectura"."""

    current_tare: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0, nullable=False)
    """Offset de tara aplicado por software (`ScaleReadService.apply_tare`/
    `clear_tare`) — se resta de cada lectura bruta para obtener el peso
    neto. Funciona con cualquier adaptador, incluso los que no soportan un
    comando de tara remota (la inmensa mayoría de básculas económicas)."""
    simulator_target_weight: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    """Solo aplica cuando `kind == 'simulator'` — peso objetivo que el
    adaptador simulado converge a devolver (ver
    `SimulatorScaleProvider`/`ScaleService.set_simulator_target_weight`)."""

    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, native_enum=False),
        default=ConnectionStatus.DISCONNECTED,
        nullable=False,
    )
    """Último estado de conexión conocido — se resetea a `DISCONNECTED`
    para todas las filas al arrancar la app, ver `ConnectionStatus`."""
    last_successful_communication_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )


class ScaleDeviceEvent(Base):
    """Entrada de historial/diagnóstico de una báscula (conexiones,
    errores, lecturas, tara, calibración) — se borra en cascada si se
    elimina el dispositivo (es solo diagnóstico, no dato contable)."""

    __tablename__ = "scale_device_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    scale_device_id: Mapped[int] = mapped_column(
        ForeignKey("scale_device_configs.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[ScaleDeviceEventType] = mapped_column(
        Enum(ScaleDeviceEventType, native_enum=False), nullable=False
    )
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class ScaleWeightRead(Base):
    """Registro centralizado de pesadas — independiente del inventario de
    dispositivos, no requiere que exista un `ScaleDeviceConfig` (una lectura
    del simulador o del adaptador genérico se registra igual), mismo
    principio que `BarcodeRead` en barcode_scanners. Es la fuente de verdad
    del historial pedido: fecha/hora, usuario, caja, producto, peso,
    unidad, báscula usada, tiempo de lectura, errores y reconexiones."""

    __tablename__ = "scale_weight_reads"

    id: Mapped[int] = mapped_column(primary_key=True)
    scale_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("scale_device_configs.id", ondelete="SET NULL"), nullable=True
    )
    """`SET NULL` (no cascada): el historial de pesadas es un registro de
    lo que pasó, no debe borrarse solo porque el dispositivo se eliminó de
    la configuración — a diferencia de `ScaleDeviceEvent`, que sí es
    diagnóstico desechable del propio dispositivo."""
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cash_register_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cash_register_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    gross_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    net_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    tare: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0, nullable=False)
    unit: Mapped[UnitOfMeasure] = mapped_column(
        Enum(UnitOfMeasure, native_enum=False), nullable=False
    )
    status: Mapped[WeightReadingStatus] = mapped_column(
        Enum(WeightReadingStatus, native_enum=False), nullable=False
    )
    is_stable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reconnected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
