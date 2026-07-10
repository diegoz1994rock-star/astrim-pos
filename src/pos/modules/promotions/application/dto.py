"""DTOs del módulo de promociones y descuentos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pos.modules.promotions.domain.enums import DiscountType, PromotionRuleType


@dataclass(frozen=True)
class PromotionRuleDTO:
    id: int
    rule_type: PromotionRuleType
    rule_value: str


@dataclass(frozen=True)
class PromotionDTO:
    id: int
    name: str
    description: str | None
    discount_type: DiscountType
    discount_value: Decimal
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    rules: list[PromotionRuleDTO]


@dataclass(frozen=True)
class AppliedDiscountDTO:
    """Descuento automático que una promoción calculó para una línea del
    carrito, identificada por `product_id` (una venta no repite el mismo
    producto en dos líneas separadas, ver `SaleViewModel`)."""

    product_id: int
    promotion_id: int
    promotion_name: str
    amount: Decimal
