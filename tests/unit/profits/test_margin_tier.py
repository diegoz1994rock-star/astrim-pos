"""Pruebas unitarias de `classify_margin` — clasificación usada por los
indicadores de color de la tabla (verde/amarillo/rojo/gris)."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.profits.domain.enums import MarginTier
from pos.modules.profits.domain.margin_tier import classify_margin


def test_none_margin_is_none_tier() -> None:
    """`None` representa "sin movimiento" o costo histórico faltante
    (N/D) — nunca se aproxima a ningún otro nivel."""
    assert classify_margin(None) is MarginTier.NONE


def test_high_margin_at_and_above_threshold() -> None:
    assert classify_margin(Decimal("30")) is MarginTier.HIGH
    assert classify_margin(Decimal("50")) is MarginTier.HIGH


def test_medium_margin_between_thresholds() -> None:
    assert classify_margin(Decimal("10")) is MarginTier.MEDIUM
    assert classify_margin(Decimal("29.99")) is MarginTier.MEDIUM


def test_low_margin_below_medium_threshold() -> None:
    assert classify_margin(Decimal("9.99")) is MarginTier.LOW
    assert classify_margin(Decimal("0")) is MarginTier.LOW


def test_negative_margin_is_low_tier() -> None:
    assert classify_margin(Decimal("-15")) is MarginTier.LOW
