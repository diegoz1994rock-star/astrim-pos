"""Pruebas de integración de PromotionService contra SQLite real."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.promotions.application.promotion_service import PromotionService
from pos.modules.promotions.domain.enums import DiscountType, PromotionRuleType
from pos.modules.promotions.infrastructure.models import DiscountApplied
from pos.modules.sales.infrastructure.models import Sale, SaleItem
from tests.integration.promotions.conftest import ProductFixture

_FRIDAY_NOON = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)  # 2026-07-10 es viernes


def test_create_promotion_rejects_empty_name(sqlite_engine: None) -> None:
    service = PromotionService()
    with pytest.raises(BusinessRuleViolationError):
        service.create_promotion(
            name="  ",
            description=None,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal(10),
        )


def test_create_promotion_rejects_percentage_over_100(sqlite_engine: None) -> None:
    service = PromotionService()
    with pytest.raises(BusinessRuleViolationError):
        service.create_promotion(
            name="Descuento imposible",
            description=None,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal(150),
        )


def test_storewide_promotion_without_rules_applies_to_any_product(
    base_product: ProductFixture,
) -> None:
    service = PromotionService()
    service.create_promotion(
        name="10% en todo",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(10),
    )

    discounts = service.compute_discounts(
        [(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON
    )

    assert len(discounts) == 1
    assert discounts[0].amount == Decimal("500.00")


def test_product_rule_only_applies_to_that_product(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Solo esta gaseosa",
        description=None,
        discount_type=DiscountType.FIXED_AMOUNT,
        discount_value=Decimal(500),
    )
    service.add_rule(
        promotion.id, rule_type=PromotionRuleType.PRODUCT, rule_value=str(base_product.product_id)
    )

    matches = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)
    no_match = service.compute_discounts([(9999, Decimal(1))], at=_FRIDAY_NOON)

    assert len(matches) == 1 and matches[0].amount == Decimal(500)
    assert no_match == []


def test_category_rule_matches_by_product_category(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Bebidas -20%",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(20),
    )
    service.add_rule(
        promotion.id,
        rule_type=PromotionRuleType.CATEGORY,
        rule_value=str(base_product.category_id),
    )

    discounts = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)

    assert len(discounts) == 1
    assert discounts[0].amount == Decimal("1000.00")


def test_min_quantity_rule_blocks_below_threshold(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Lleva 3 o más",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(15),
    )
    service.add_rule(promotion.id, rule_type=PromotionRuleType.MIN_QUANTITY, rule_value="3")

    below = service.compute_discounts([(base_product.product_id, Decimal(2))], at=_FRIDAY_NOON)
    at_threshold = service.compute_discounts(
        [(base_product.product_id, Decimal(3))], at=_FRIDAY_NOON
    )

    assert below == []
    assert len(at_threshold) == 1


def test_day_of_week_rule_only_applies_on_listed_days(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Viernes de descuento",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(10),
    )
    service.add_rule(promotion.id, rule_type=PromotionRuleType.DAY_OF_WEEK, rule_value="fri,sat")

    friday = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)
    monday = service.compute_discounts(
        [(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON - timedelta(days=4)
    )

    assert len(friday) == 1
    assert monday == []


def test_time_range_rule_only_applies_within_the_window(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Happy hour",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(10),
    )
    service.add_rule(
        promotion.id, rule_type=PromotionRuleType.TIME_RANGE, rule_value="18:00-20:00"
    )

    inside = service.compute_discounts(
        [(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON.replace(hour=19)
    )
    outside = service.compute_discounts(
        [(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON.replace(hour=10)
    )

    assert len(inside) == 1
    assert outside == []


def test_inactive_promotion_does_not_apply(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Desactivada",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(50),
    )
    service.set_active(promotion.id, False)

    discounts = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)

    assert discounts == []


def test_expired_promotion_does_not_apply(base_product: ProductFixture) -> None:
    service = PromotionService()
    with session_scope() as session:
        from pos.modules.promotions.infrastructure.repository import PromotionRepository

        repo = PromotionRepository(session)
        repo.create_promotion(
            name="Ya vencida",
            description=None,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal(50),
            starts_at=_FRIDAY_NOON - timedelta(days=30),
            ends_at=_FRIDAY_NOON - timedelta(days=1),
        )

    discounts = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)

    assert discounts == []


def test_when_multiple_promotions_match_the_larger_discount_wins(
    base_product: ProductFixture,
) -> None:
    service = PromotionService()
    service.create_promotion(
        name="10% en todo",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(10),
    )
    service.create_promotion(
        name="30% en todo",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(30),
    )

    discounts = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)

    assert len(discounts) == 1
    assert discounts[0].amount == Decimal("1500.00")


def test_remove_rule_makes_promotion_storewide_again(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Temporal",
        description=None,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal(10),
    )
    with_rule = service.add_rule(
        promotion.id, rule_type=PromotionRuleType.PRODUCT, rule_value="99999"
    )
    rule_id = with_rule.rules[0].id

    before = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)
    service.remove_rule(promotion.id, rule_id)
    after = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)

    assert before == []
    assert len(after) == 1


def test_record_applied_discounts_persists_audit_trail(base_product: ProductFixture) -> None:
    service = PromotionService()
    promotion = service.create_promotion(
        name="Auditable",
        description=None,
        discount_type=DiscountType.FIXED_AMOUNT,
        discount_value=Decimal(200),
    )
    discounts = service.compute_discounts([(base_product.product_id, Decimal(1))], at=_FRIDAY_NOON)
    assert discounts[0].promotion_id == promotion.id

    with session_scope() as session:
        sale = Sale()
        session.add(sale)
        session.flush()
        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=base_product.product_id,
            quantity=Decimal(1),
            unit_price=Decimal("5000"),
            line_total=Decimal("4800"),
        )
        session.add(sale_item)
        session.flush()
        sale_id, sale_item_id = sale.id, sale_item.id

    service.record_applied_discounts(
        sale_id=sale_id,
        sale_item_ids_by_product={base_product.product_id: sale_item_id},
        discounts=discounts,
    )

    with session_scope() as session:
        rows = session.query(DiscountApplied).all()
    assert len(rows) == 1
    assert rows[0].sale_id == sale_id
    assert rows[0].sale_item_id == sale_item_id
    assert rows[0].amount == Decimal(200)
