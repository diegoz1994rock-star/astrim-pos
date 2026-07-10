"""Modelos SQLAlchemy de promociones, sus reglas y los descuentos ya aplicados a ventas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.promotions.domain.enums import DiscountType, PromotionRuleType


class Promotion(Base, TimestampMixin):
    """Promoción o descuento configurable desde la UI, sin tocar código."""

    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, native_enum=False), nullable=False
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rules: Mapped[list[PromotionRule]] = relationship(
        back_populates="promotion", cascade="all, delete-orphan"
    )


class PromotionRule(Base):
    """Condición de aplicación de una promoción. Ver `PromotionRuleType` para
    cómo interpretar `rule_value` según el tipo de regla."""

    __tablename__ = "promotion_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    promotion_id: Mapped[int] = mapped_column(ForeignKey("promotions.id"), nullable=False)
    rule_type: Mapped[PromotionRuleType] = mapped_column(
        Enum(PromotionRuleType, native_enum=False), nullable=False
    )
    rule_value: Mapped[str] = mapped_column(String(255), nullable=False)

    promotion: Mapped[Promotion] = relationship(back_populates="rules")


class DiscountApplied(Base):
    """Descuento efectivamente aplicado a una venta o línea de venta.

    Queda registrado de forma independiente a `Promotion` para que el
    historial de la venta no cambie si la promoción se edita o desactiva
    después.
    """

    __tablename__ = "discounts_applied"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), nullable=False)
    promotion_id: Mapped[int | None] = mapped_column(ForeignKey("promotions.id"), nullable=True)
    sale_item_id: Mapped[int | None] = mapped_column(ForeignKey("sale_items.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
