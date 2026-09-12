"""Pruebas unitarias de `resolve_range` — única fuente de verdad del
rango de fechas para las 6 pestañas de Ganancias. Casos límite: fin de
mes, fin de trimestre, año bisiesto, cruce de año en la semana."""

from __future__ import annotations

from datetime import date

import pytest

from pos.modules.profits.domain.date_ranges import resolve_range
from pos.modules.profits.domain.enums import DateRangePreset


def test_daily_returns_same_day_twice() -> None:
    assert resolve_range(DateRangePreset.DAILY, date(2026, 7, 16)) == (
        date(2026, 7, 16),
        date(2026, 7, 16),
    )


def test_weekly_returns_monday_to_sunday() -> None:
    # 2026-07-16 es jueves
    start, end = resolve_range(DateRangePreset.WEEKLY, date(2026, 7, 16))
    assert start == date(2026, 7, 13)  # lunes
    assert end == date(2026, 7, 19)  # domingo
    assert start.weekday() == 0
    assert end.weekday() == 6


def test_weekly_crosses_year_boundary_correctly() -> None:
    start, end = resolve_range(DateRangePreset.WEEKLY, date(2026, 1, 1))
    assert start == date(2025, 12, 29)
    assert end == date(2026, 1, 4)


def test_monthly_returns_first_to_last_day() -> None:
    assert resolve_range(DateRangePreset.MONTHLY, date(2026, 7, 16)) == (
        date(2026, 7, 1),
        date(2026, 7, 31),
    )


def test_monthly_handles_leap_february() -> None:
    assert resolve_range(DateRangePreset.MONTHLY, date(2024, 2, 15)) == (
        date(2024, 2, 1),
        date(2024, 2, 29),
    )


def test_monthly_handles_non_leap_february() -> None:
    assert resolve_range(DateRangePreset.MONTHLY, date(2025, 2, 15)) == (
        date(2025, 2, 1),
        date(2025, 2, 28),
    )


@pytest.mark.parametrize(
    ("reference", "expected_start", "expected_end"),
    [
        (date(2026, 1, 15), date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 15), date(2026, 4, 1), date(2026, 6, 30)),
        (date(2026, 7, 15), date(2026, 7, 1), date(2026, 9, 30)),
        (date(2026, 12, 31), date(2026, 10, 1), date(2026, 12, 31)),
    ],
)
def test_quarterly_returns_correct_quarter(
    reference: date, expected_start: date, expected_end: date
) -> None:
    assert resolve_range(DateRangePreset.QUARTERLY, reference) == (expected_start, expected_end)


def test_semiannual_first_half() -> None:
    assert resolve_range(DateRangePreset.SEMIANNUAL, date(2026, 3, 1)) == (
        date(2026, 1, 1),
        date(2026, 6, 30),
    )


def test_semiannual_second_half() -> None:
    assert resolve_range(DateRangePreset.SEMIANNUAL, date(2026, 9, 1)) == (
        date(2026, 7, 1),
        date(2026, 12, 31),
    )


def test_annual_returns_full_year() -> None:
    assert resolve_range(DateRangePreset.ANNUAL, date(2026, 7, 16)) == (
        date(2026, 1, 1),
        date(2026, 12, 31),
    )
