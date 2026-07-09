"""Modelos SQLAlchemy de compras: órdenes de compra, ítems y recepción de mercancía."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import AuditedEntity, Base, utc_now
from pos.modules.purchasing.domain.enums import PurchaseOrderStatus


class PurchaseOrder(Base, AuditedEntity):
    """Orden de compra a un proveedor."""

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, native_enum=False),
        default=PurchaseOrderStatus.DRAFT,
        nullable=False,
    )
    order_date: Mapped[date] = mapped_column(nullable=False)
    expected_date: Mapped[date | None] = mapped_column(nullable=True)

    items: Mapped[list[PurchaseOrderItem]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderItem(Base):
    """Línea de producto dentro de una orden de compra."""

    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")


class PurchaseReceipt(Base):
    """Recepción física de una orden de compra: genera movimientos de
    entrada en Inventario a través del bus de eventos (`PurchaseReceivedEvent`)."""

    __tablename__ = "purchase_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    received_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
