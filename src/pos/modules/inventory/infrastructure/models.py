"""Modelos SQLAlchemy de inventario: bodegas, existencias, movimientos, lotes y alertas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.modules.inventory.domain.enums import StockMovementType


class Warehouse(Base, TimestampMixin):
    """Bodega o punto de almacenamiento (puede ser una sola para negocios pequeños)."""

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StockLevel(Base):
    """Existencia actual de un producto en una bodega.

    Se mantiene como saldo materializado (no se recalcula sumando
    `stock_movements` en cada consulta) por rendimiento; se actualiza de
    forma transaccional junto con la inserción del movimiento que lo origina.
    """

    __tablename__ = "stock_levels"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_stock_product_warehouse"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class StockMovement(Base):
    """Movimiento de inventario: entrada, salida, transferencia o ajuste.

    `reference_document_type` + `reference_document_id` apuntan al
    documento que originó el movimiento (ej. `"sale"` + id de la venta,
    `"purchase_receipt"` + id de la recepción), sin declarar una FK dura
    porque el documento origen puede ser de distintos módulos.
    """

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType, native_enum=False), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    """Siempre positiva; el signo del efecto sobre el stock lo determina `movement_type`."""

    reference_document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_document_id: Mapped[int | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ProductBatch(Base):
    """Lote de un producto con fecha de vencimiento, para control FEFO
    (first-expired, first-out) y alertas de vencimiento."""

    __tablename__ = "product_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    batch_code: Mapped[str] = mapped_column(String(50), nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)


class StockAlertConfig(Base):
    """Configuración de alerta de stock mínimo/agotado por producto."""

    __tablename__ = "stock_alerts_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), unique=True, nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    notify_on_zero: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
