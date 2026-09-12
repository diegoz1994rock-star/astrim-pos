"""Pruebas de `today_utc_bounds`: el rango UTC de "hoy" debe calcularse a
partir de la medianoche LOCAL, no de la medianoche UTC — una venta hecha a
última hora de la tarde en un huso horario de offset negativo (ej.
Colombia, UTC-5) ya cae en el día UTC siguiente."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from pos.core.database.base import today_utc_bounds

_BOGOTA = timezone(timedelta(hours=-5))


def test_today_utc_bounds_covers_local_midnight_to_midnight() -> None:
    reference = datetime(2026, 1, 1, 23, 30, tzinfo=_BOGOTA)

    start, end = today_utc_bounds(reference)

    assert start.tzinfo is UTC
    assert end.tzinfo is UTC
    assert start == datetime(2026, 1, 1, 5, 0, tzinfo=UTC)  # medianoche Bogotá = 05:00 UTC
    assert end.date() == datetime(2026, 1, 2, 4, 59, tzinfo=UTC).date()


def test_today_utc_bounds_includes_late_local_sale_even_though_utc_day_already_changed() -> None:
    reference = datetime(2026, 1, 1, 23, 30, tzinfo=_BOGOTA)
    start, end = today_utc_bounds(reference)

    sale_at_2345_bogota_utc = datetime(2026, 1, 1, 23, 45, tzinfo=_BOGOTA).astimezone(UTC)

    assert start <= sale_at_2345_bogota_utc <= end


def test_today_utc_bounds_excludes_sale_from_next_local_day() -> None:
    reference = datetime(2026, 1, 1, 23, 30, tzinfo=_BOGOTA)
    start, end = today_utc_bounds(reference)

    sale_at_0015_next_day_bogota_utc = datetime(2026, 1, 2, 0, 15, tzinfo=_BOGOTA).astimezone(UTC)

    assert not (start <= sale_at_0015_next_day_bogota_utc <= end)


def test_today_utc_bounds_excludes_sale_from_previous_local_day() -> None:
    reference = datetime(2026, 1, 1, 0, 30, tzinfo=_BOGOTA)
    start, end = today_utc_bounds(reference)

    sale_at_2345_previous_day_bogota_utc = datetime(
        2025, 12, 31, 23, 45, tzinfo=_BOGOTA
    ).astimezone(UTC)

    assert not (start <= sale_at_2345_previous_day_bogota_utc <= end)


def test_today_utc_bounds_without_reference_uses_current_time() -> None:
    start, end = today_utc_bounds()

    assert start.tzinfo is UTC
    assert end.tzinfo is UTC
    assert start < end
    assert (end - start) < timedelta(days=1, hours=1)
