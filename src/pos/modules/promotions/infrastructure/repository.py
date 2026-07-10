"""Acceso a datos de promociones, sus reglas y los descuentos aplicados."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pos.modules.promotions.domain.enums import DiscountType, PromotionRuleType
from pos.modules.promotions.infrastructure.models import (
    DiscountApplied,
    Promotion,
    PromotionRule,
)


class PromotionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_promotions(self) -> list[Promotion]:
        return list(
            self._session.scalars(
                select(Promotion).options(selectinload(Promotion.rules)).order_by(Promotion.name)
            )
        )

    def list_active_promotions(self) -> list[Promotion]:
        return list(
            self._session.scalars(
                select(Promotion)
                .options(selectinload(Promotion.rules))
                .where(Promotion.is_active)
            )
        )

    def get_promotion(self, promotion_id: int) -> Promotion | None:
        return self._session.scalar(
            select(Promotion)
            .options(selectinload(Promotion.rules))
            .where(Promotion.id == promotion_id)
        )

    def create_promotion(
        self,
        *,
        name: str,
        description: str | None,
        discount_type: DiscountType,
        discount_value: Decimal,
        starts_at: datetime | None,
        ends_at: datetime | None,
    ) -> Promotion:
        promotion = Promotion(
            name=name,
            description=description,
            discount_type=discount_type,
            discount_value=discount_value,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=True,
        )
        self._session.add(promotion)
        self._session.flush()
        return promotion

    def set_active(self, promotion: Promotion, is_active: bool) -> None:
        promotion.is_active = is_active

    def add_rule(
        self, promotion: Promotion, *, rule_type: PromotionRuleType, rule_value: str
    ) -> PromotionRule:
        """Agrega la regla vía `promotion.rules.append(...)`, no asignando
        `promotion_id` a mano: así la colección en memoria de `promotion`
        queda al día de inmediato (importa porque `PromotionService.add_rule`
        devuelve el DTO reconstruido a partir de este mismo objeto, dentro
        de la misma transacción — sin el `append`, `promotion.rules` seguía
        reflejando el estado de antes de agregar la regla)."""
        rule = PromotionRule(rule_type=rule_type, rule_value=rule_value)
        promotion.rules.append(rule)
        self._session.flush()
        return rule

    def remove_rule(self, promotion: Promotion, rule_id: int) -> None:
        rule = self._session.get(PromotionRule, rule_id)
        if rule is not None and rule in promotion.rules:
            promotion.rules.remove(rule)
            self._session.delete(rule)

    def record_applied_discount(
        self,
        *,
        sale_id: int,
        promotion_id: int | None,
        sale_item_id: int | None,
        amount: Decimal,
    ) -> DiscountApplied:
        applied = DiscountApplied(
            sale_id=sale_id, promotion_id=promotion_id, sale_item_id=sale_item_id, amount=amount
        )
        self._session.add(applied)
        self._session.flush()
        return applied
