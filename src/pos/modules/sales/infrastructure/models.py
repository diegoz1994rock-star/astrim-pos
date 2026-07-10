"""Modelos SQLAlchemy de ventas: encabezado, ítems y pagos.

`cash_session_id` referencia `cash_sessions.id` (módulo `cash_register`)
por nombre de tabla, sin importar ese módulo, según ARCHITECTURE.md §12b.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import AuditedEntity, Base, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus, SaleType


class Sale(Base, AuditedEntity):
    """Encabezado de una venta."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    cash_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_sessions.id"), nullable=True
    )
    status: Mapped[SaleStatus] = mapped_column(
        Enum(SaleStatus, native_enum=False), default=SaleStatus.DRAFT, nullable=False
    )
    sale_type: Mapped[SaleType] = mapped_column(
        Enum(SaleType, native_enum=False), default=SaleType.COUNTER, nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    items: Mapped[list[SaleItem]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )
    payments: Mapped[list[SalePayment]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )


class SaleItem(Base):
    """Línea de producto dentro de una venta."""

    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="items")


class SalePayment(Base):
    """Pago aplicado a una venta. Una venta puede tener varios (pago mixto)."""

    __tablename__ = "sale_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="payments")
