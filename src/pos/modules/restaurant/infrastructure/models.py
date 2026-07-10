"""Modelos SQLAlchemy de mesas y pedidos.

`sale_id` en `BillSplit` referencia `sales.id` (módulo `sales`) sin
importarlo, según ARCHITECTURE.md §12b.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.restaurant.domain.enums import (
    OrderItemStatus,
    OrderStatus,
    OrderType,
    TableSessionStatus,
    TableStatus,
)


class DiningTable(Base, TimestampMixin):
    """Mesa física del restaurante."""

    __tablename__ = "dining_tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[TableStatus] = mapped_column(
        Enum(TableStatus, native_enum=False), default=TableStatus.FREE, nullable=False
    )


class TableSession(Base):
    """Ocupación de una mesa: desde que llega el cliente hasta que se cierra
    la cuenta. Permite cambio y unión de mesas reasignando `table_id` o
    creando varias filas que comparten pedidos (ver `BillSplit`)."""

    __tablename__ = "table_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("dining_tables.id"), nullable=False)
    waiter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[TableSessionStatus] = mapped_column(
        Enum(TableSessionStatus, native_enum=False), default=TableSessionStatus.OPEN, nullable=False
    )
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Order(Base, TimestampMixin):
    """Pedido. `table_session_id` es nulo para pedidos para llevar, a
    domicilio o rápidos que no ocupan una mesa."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("table_sessions.id"), nullable=True
    )
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType, native_enum=False), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False), default=OrderStatus.PENDING, nullable=False
    )

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    """Ítem de un pedido, con estado propio de cocina (PROJECT_SPEC.md, "COCINA")."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[OrderItemStatus] = mapped_column(
        Enum(OrderItemStatus, native_enum=False), default=OrderItemStatus.PENDING, nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="items")


class OrderItemStatusHistory(Base):
    """Historial de cambios de estado de un ítem de pedido, para trazabilidad
    en la pantalla de cocina y cálculo de tiempos de preparación."""

    __tablename__ = "order_item_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    status: Mapped[OrderItemStatus] = mapped_column(
        Enum(OrderItemStatus, native_enum=False), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class BillSplit(Base):
    """División de cuenta de una sesión de mesa en varias ventas independientes."""

    __tablename__ = "bill_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_session_id: Mapped[int] = mapped_column(ForeignKey("table_sessions.id"), nullable=False)
    split_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"), nullable=True)
