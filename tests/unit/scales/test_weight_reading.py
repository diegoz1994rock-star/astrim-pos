"""Pruebas de dominio puro de `weight_reading`: conversión de unidades
(kg/g/lb/oz), clasificación de una lectura y `StabilityTracker`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pos.modules.scales.domain.enums import UnitOfMeasure, WeightReadingStatus
from pos.modules.scales.domain.weight_reading import (
    StabilityTracker,
    classify_reading,
    convert_weight,
)

# -- convert_weight -----------------------------------------------------------


def test_convert_weight_same_unit_is_identity() -> None:
    assert convert_weight(Decimal("2.350"), UnitOfMeasure.KG, UnitOfMeasure.KG) == Decimal("2.350")


def test_convert_weight_kg_to_g() -> None:
    result = convert_weight(Decimal("2.350"), UnitOfMeasure.KG, UnitOfMeasure.G)
    assert result == Decimal("2350.000")


def test_convert_weight_g_to_kg() -> None:
    assert convert_weight(Decimal("2350"), UnitOfMeasure.G, UnitOfMeasure.KG) == Decimal("2.350")


def test_convert_weight_kg_to_lb() -> None:
    # 1 kg = 2.20462262185 lb (exacto por definición de libra internacional)
    result = convert_weight(Decimal("1"), UnitOfMeasure.KG, UnitOfMeasure.LB)
    assert abs(result - Decimal("2.20462262185")) < Decimal("0.0000001")


def test_convert_weight_lb_to_kg_round_trip() -> None:
    original = Decimal("5.000")
    grams = convert_weight(original, UnitOfMeasure.KG, UnitOfMeasure.LB)
    back = convert_weight(grams, UnitOfMeasure.LB, UnitOfMeasure.KG)
    assert abs(back - original) < Decimal("0.000001")


def test_convert_weight_oz_to_g() -> None:
    # 1 oz = 28.349523125 g exacto
    assert convert_weight(Decimal("1"), UnitOfMeasure.OZ, UnitOfMeasure.G) == Decimal(
        "28.349523125"
    )


def test_convert_weight_kg_to_oz_round_trip() -> None:
    original = Decimal("1.500")
    ounces = convert_weight(original, UnitOfMeasure.KG, UnitOfMeasure.OZ)
    back = convert_weight(ounces, UnitOfMeasure.OZ, UnitOfMeasure.KG)
    assert abs(back - original) < Decimal("0.000001")


# -- classify_reading -----------------------------------------------------------


def test_classify_reading_negative_weight() -> None:
    assert classify_reading(Decimal("-0.5")) is WeightReadingStatus.NEGATIVE


def test_classify_reading_zero_weight() -> None:
    assert classify_reading(Decimal("0")) is WeightReadingStatus.ZERO


def test_classify_reading_plausible_weight_with_no_range_is_none() -> None:
    assert classify_reading(Decimal("2.350")) is None


def test_classify_reading_below_product_minimum() -> None:
    status = classify_reading(Decimal("0.050"), min_weight=Decimal("0.100"))
    assert status is WeightReadingStatus.OUT_OF_RANGE


def test_classify_reading_above_product_maximum() -> None:
    status = classify_reading(Decimal("15.000"), max_weight=Decimal("10.000"))
    assert status is WeightReadingStatus.OUT_OF_RANGE


def test_classify_reading_within_product_range_is_none() -> None:
    status = classify_reading(
        Decimal("2.500"), min_weight=Decimal("0.100"), max_weight=Decimal("10.000")
    )
    assert status is None


# -- StabilityTracker -----------------------------------------------------------


def test_stability_tracker_not_stable_on_first_reading() -> None:
    tracker = StabilityTracker(tolerance=Decimal("0.005"), min_stable_seconds=Decimal("0.5"))
    now = datetime.now(UTC)
    assert tracker.push(Decimal("2.350"), now=now) is False


def test_stability_tracker_becomes_stable_after_min_seconds_within_tolerance() -> None:
    tracker = StabilityTracker(tolerance=Decimal("0.005"), min_stable_seconds=Decimal("0.5"))
    start = datetime.now(UTC)
    assert tracker.push(Decimal("2.350"), now=start) is False
    assert tracker.push(Decimal("2.351"), now=start + timedelta(seconds=0.2)) is False
    assert tracker.push(Decimal("2.350"), now=start + timedelta(seconds=0.6)) is True


def test_stability_tracker_resets_when_weight_jumps_beyond_tolerance() -> None:
    tracker = StabilityTracker(tolerance=Decimal("0.005"), min_stable_seconds=Decimal("0.5"))
    start = datetime.now(UTC)
    tracker.push(Decimal("2.350"), now=start)
    tracker.push(Decimal("2.350"), now=start + timedelta(seconds=0.6))
    # Un salto brusco (alguien pone/saca algo del plato) reinicia el conteo.
    assert tracker.push(Decimal("5.000"), now=start + timedelta(seconds=0.65)) is False
    assert tracker.push(Decimal("5.000"), now=start + timedelta(seconds=0.7)) is False
    assert tracker.push(Decimal("5.000"), now=start + timedelta(seconds=1.2)) is True


def test_stability_tracker_reset_clears_state() -> None:
    tracker = StabilityTracker(tolerance=Decimal("0.005"), min_stable_seconds=Decimal("0.5"))
    start = datetime.now(UTC)
    tracker.push(Decimal("2.350"), now=start)
    tracker.push(Decimal("2.350"), now=start + timedelta(seconds=0.6))
    tracker.reset()
    assert tracker.push(Decimal("2.350"), now=start + timedelta(seconds=0.65)) is False
