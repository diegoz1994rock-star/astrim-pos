"""Pruebas de la traducción entre las 4 frecuencias amigables que ve el
usuario y la expresión cron interna — el usuario nunca debe ver cron."""

from __future__ import annotations

from pos.modules.backups.application.schedule_translator import (
    build_cron,
    describe_schedule,
    parse_schedule,
)
from pos.modules.backups.domain.enums import ScheduleFrequency


def test_build_cron_hourly_ignores_time() -> None:
    assert build_cron(ScheduleFrequency.HOURLY, 13, 45) == "0 * * * *"


def test_build_cron_every_six_hours_ignores_time() -> None:
    assert build_cron(ScheduleFrequency.EVERY_SIX_HOURS, 5, 30) == "0 */6 * * *"


def test_build_cron_daily_uses_time() -> None:
    assert build_cron(ScheduleFrequency.DAILY, 2, 0) == "0 2 * * *"
    assert build_cron(ScheduleFrequency.DAILY, 20, 30) == "30 20 * * *"


def test_build_cron_weekly_monday_uses_time() -> None:
    assert build_cron(ScheduleFrequency.WEEKLY_MONDAY, 8, 15) == "15 8 * * 1"


def test_parse_schedule_round_trips_all_frequencies() -> None:
    cases = [
        (ScheduleFrequency.HOURLY, 0, 0),
        (ScheduleFrequency.EVERY_SIX_HOURS, 0, 0),
        (ScheduleFrequency.DAILY, 2, 0),
        (ScheduleFrequency.DAILY, 23, 59),
        (ScheduleFrequency.WEEKLY_MONDAY, 20, 30),
    ]
    for frequency, hour, minute in cases:
        cron = build_cron(frequency, hour, minute)
        assert parse_schedule(cron) == (frequency, hour, minute)


def test_parse_schedule_returns_none_for_unrecognized_cron() -> None:
    assert parse_schedule("*/15 * * * *") is None


def test_parse_schedule_returns_none_for_none() -> None:
    assert parse_schedule(None) is None


def test_describe_schedule_no_configuration() -> None:
    assert describe_schedule(None) == "No hay backups automáticos configurados."


def test_describe_schedule_hourly() -> None:
    assert describe_schedule("0 * * * *") == "Backup automático cada hora"


def test_describe_schedule_every_six_hours() -> None:
    assert describe_schedule("0 */6 * * *") == "Backup automático cada 6 horas"


def test_describe_schedule_daily_formats_time_as_12h() -> None:
    assert (
        describe_schedule("0 2 * * *") == "Backup automático todos los días a las 02:00 AM"
    )


def test_describe_schedule_weekly_monday_formats_time_as_12h() -> None:
    assert (
        describe_schedule("30 20 * * 1")
        == "Backup automático todos los lunes a las 08:30 PM"
    )


def test_describe_schedule_unrecognized_cron_never_shows_raw_cron() -> None:
    description = describe_schedule("*/15 * * * *")
    assert "*/15" not in description
    assert description == "Backup automático (programación personalizada)."
