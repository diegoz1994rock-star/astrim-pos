"""Caso de uso de promociones y descuentos (PROJECT_SPEC.md, "PROMOCIONES").

`compute_discounts` es la pieza que consume Ventas (composición en la capa
de presentación, `SaleViewModel` — ver ARCHITECTURE.md §12b: leer datos de
otro módulo vía su repositorio es un patrón ya establecido, ej.
`SalesService` ya usa `ProductRepository` directamente): dado el carrito
actual, calcula qué promociones activas aplican y cuánto descuentan cada
línea, sin persistir nada. `record_applied_discounts` sí persiste, y se
llama una vez la venta ya se completó — el descuento aplicado queda
congelado en `discounts_applied` aunque la promoción se edite o desactive
después.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.products.infrastructure.product_repository import ProductRepository
from pos.modules.promotions.application.dto import (
    AppliedDiscountDTO,
    PromotionDTO,
    PromotionRuleDTO,
)
from pos.modules.promotions.domain.enums import DiscountType, PromotionRuleType
from pos.modules.promotions.infrastructure.models import Promotion, PromotionRule
from pos.modules.promotions.infrastructure.repository import PromotionRepository

_DAY_CODES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _to_dto(promotion: Promotion) -> PromotionDTO:
    return PromotionDTO(
        id=promotion.id,
        name=promotion.name,
        description=promotion.description,
        discount_type=promotion.discount_type,
        discount_value=promotion.discount_value,
        starts_at=promotion.starts_at,
        ends_at=promotion.ends_at,
        is_active=promotion.is_active,
        rules=[
            PromotionRuleDTO(id=rule.id, rule_type=rule.rule_type, rule_value=rule.rule_value)
            for rule in promotion.rules
        ],
    )


def _rules_by_type(
    rules: list[PromotionRule],
) -> dict[PromotionRuleType, list[PromotionRule]]:
    by_type: dict[PromotionRuleType, list[PromotionRule]] = {}
    for rule in rules:
        by_type.setdefault(rule.rule_type, []).append(rule)
    return by_type


def _within_schedule(promotion: Promotion, at: datetime) -> bool:
    if promotion.starts_at is not None and at < promotion.starts_at:
        return False
    return not (promotion.ends_at is not None and at > promotion.ends_at)


def _conditions_met(
    by_type: dict[PromotionRuleType, list[PromotionRule]], *, quantity: Decimal, at: datetime
) -> bool:
    for rule in by_type.get(PromotionRuleType.DAY_OF_WEEK, []):
        allowed = {code.strip().lower() for code in rule.rule_value.split(",")}
        if _DAY_CODES[at.weekday()] not in allowed:
            return False
    for rule in by_type.get(PromotionRuleType.TIME_RANGE, []):
        start_raw, _, end_raw = rule.rule_value.partition("-")
        start_time = datetime.strptime(start_raw.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_raw.strip(), "%H:%M").time()
        if not (start_time <= at.time() <= end_time):
            return False
    for rule in by_type.get(PromotionRuleType.MIN_QUANTITY, []):
        if quantity < Decimal(rule.rule_value):
            return False
    return True


def _targets_product(
    by_type: dict[PromotionRuleType, list[PromotionRule]],
    *,
    product_id: int,
    category_id: int | None,
    is_combo: bool,
) -> bool:
    targeting_rules = (
        by_type.get(PromotionRuleType.PRODUCT, [])
        + by_type.get(PromotionRuleType.CATEGORY, [])
        + by_type.get(PromotionRuleType.COMBO, [])
    )
    if not targeting_rules:
        return True  # sin reglas de objetivo: promoción para toda la tienda
    for rule in by_type.get(PromotionRuleType.PRODUCT, []):
        if int(rule.rule_value) == product_id:
            return True
    if category_id is not None:
        for rule in by_type.get(PromotionRuleType.CATEGORY, []):
            if int(rule.rule_value) == category_id:
                return True
    if is_combo:
        for rule in by_type.get(PromotionRuleType.COMBO, []):
            if int(rule.rule_value) == product_id:
                return True
    return False


class PromotionService:
    def list_promotions(self) -> list[PromotionDTO]:
        with session_scope() as session:
            return [_to_dto(p) for p in PromotionRepository(session).list_promotions()]

    def create_promotion(
        self,
        *,
        name: str,
        description: str | None,
        discount_type: DiscountType,
        discount_value: Decimal,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> PromotionDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la promoción no puede estar vacío.")
        if discount_value <= 0:
            raise BusinessRuleViolationError("El valor del descuento debe ser mayor que cero.")
        if discount_type is DiscountType.PERCENTAGE and discount_value > 100:
            raise BusinessRuleViolationError("Un descuento porcentual no puede superar el 100%.")

        with session_scope() as session:
            promotion = PromotionRepository(session).create_promotion(
                name=name,
                description=description,
                discount_type=discount_type,
                discount_value=discount_value,
                starts_at=starts_at,
                ends_at=ends_at,
            )
            return _to_dto(promotion)

    def set_active(self, promotion_id: int, is_active: bool) -> PromotionDTO:
        with session_scope() as session:
            repo = PromotionRepository(session)
            promotion = repo.get_promotion(promotion_id)
            if promotion is None:
                raise NotFoundError(f"No existe la promoción con id={promotion_id}.")
            repo.set_active(promotion, is_active)
            return _to_dto(promotion)

    def add_rule(
        self, promotion_id: int, *, rule_type: PromotionRuleType, rule_value: str
    ) -> PromotionDTO:
        rule_value = rule_value.strip()
        if not rule_value:
            raise BusinessRuleViolationError("El valor de la regla no puede estar vacío.")
        with session_scope() as session:
            repo = PromotionRepository(session)
            promotion = repo.get_promotion(promotion_id)
            if promotion is None:
                raise NotFoundError(f"No existe la promoción con id={promotion_id}.")
            repo.add_rule(promotion, rule_type=rule_type, rule_value=rule_value)
            return _to_dto(promotion)

    def remove_rule(self, promotion_id: int, rule_id: int) -> PromotionDTO:
        with session_scope() as session:
            repo = PromotionRepository(session)
            promotion = repo.get_promotion(promotion_id)
            if promotion is None:
                raise NotFoundError(f"No existe la promoción con id={promotion_id}.")
            repo.remove_rule(promotion, rule_id)
            return _to_dto(promotion)

    def compute_discounts(
        self, lines: list[tuple[int, Decimal]], *, at: datetime | None = None
    ) -> list[AppliedDiscountDTO]:
        """Calcula el descuento automático de cada línea `(product_id, cantidad)`
        según las promociones activas. Si más de una promoción aplica a la
        misma línea, se usa la de mayor descuento (no se acumulan) — evita
        descuentos compuestos inesperados sin una regla explícita de
        apilamiento, que el spec no pide."""
        evaluation_time = at or datetime.now(UTC)
        results: dict[int, AppliedDiscountDTO] = {}

        with session_scope() as session:
            product_repo = ProductRepository(session)
            promotion_repo = PromotionRepository(session)
            active_promotions = [
                p
                for p in promotion_repo.list_active_promotions()
                if _within_schedule(p, evaluation_time)
            ]
            if not active_promotions:
                return []

            for product_id, quantity in lines:
                product = product_repo.get(product_id)
                if product is None:
                    continue
                line_subtotal = product.unit_price * quantity
                best: AppliedDiscountDTO | None = None

                for promotion in active_promotions:
                    by_type = _rules_by_type(promotion.rules)
                    if not _targets_product(
                        by_type,
                        product_id=product_id,
                        category_id=product.category_id,
                        is_combo=product.product_type.value == "combo",
                    ):
                        continue
                    if not _conditions_met(by_type, quantity=quantity, at=evaluation_time):
                        continue

                    if promotion.discount_type is DiscountType.PERCENTAGE:
                        amount = (line_subtotal * promotion.discount_value / Decimal(100)).quantize(
                            Decimal("0.01")
                        )
                    else:
                        amount = min(promotion.discount_value, line_subtotal)

                    if best is None or amount > best.amount:
                        best = AppliedDiscountDTO(
                            product_id=product_id,
                            promotion_id=promotion.id,
                            promotion_name=promotion.name,
                            amount=amount,
                        )

                if best is not None:
                    results[product_id] = best

        return list(results.values())

    def record_applied_discounts(
        self,
        *,
        sale_id: int,
        sale_item_ids_by_product: dict[int, int],
        discounts: list[AppliedDiscountDTO],
    ) -> None:
        """Persiste el rastro de auditoría de qué promoción causó qué
        descuento en una venta ya completada (`discounts_applied`)."""
        with session_scope() as session:
            repo = PromotionRepository(session)
            for discount in discounts:
                repo.record_applied_discount(
                    sale_id=sale_id,
                    promotion_id=discount.promotion_id,
                    sale_item_id=sale_item_ids_by_product.get(discount.product_id),
                    amount=discount.amount,
                )
