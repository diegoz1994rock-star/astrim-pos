"""Enumeraciones de dominio del módulo de promociones y descuentos."""

from __future__ import annotations

import enum


class DiscountType(enum.Enum):
    """Tipo de valor de una promoción."""

    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"


class PromotionRuleType(enum.Enum):
    """A qué aplica una regla de promoción. `rule_value` en `PromotionRule`
    interpreta su contenido según este tipo (ej. PRODUCT → id de producto,
    DAY_OF_WEEK → "mon,tue,wed")."""

    PRODUCT = "product"
    CATEGORY = "category"
    COMBO = "combo"
    MIN_QUANTITY = "min_quantity"
    DAY_OF_WEEK = "day_of_week"
    TIME_RANGE = "time_range"
