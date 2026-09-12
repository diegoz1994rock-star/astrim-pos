"""Traduce entre las 4 frecuencias amigables que ve el usuario y la
expresión cron que consume `BackupScheduler` — el usuario nunca ve ni
escribe cron (ver `presentation/schedule_backup_dialog.py`)."""

from __future__ import annotations

import re

from pos.modules.backups.domain.enums import ScheduleFrequency

_HOURLY_CRON = "0 * * * *"
_EVERY_SIX_HOURS_CRON = "0 */6 * * *"
_DAILY_PATTERN = re.compile(r"^(\d{1,2}) (\d{1,2}) \* \* \*$")
_WEEKLY_MONDAY_PATTERN = re.compile(r"^(\d{1,2}) (\d{1,2}) \* \* 1$")


def build_cron(frequency: ScheduleFrequency, hour: int, minute: int) -> str:
    if frequency is ScheduleFrequency.HOURLY:
        return _HOURLY_CRON
    if frequency is ScheduleFrequency.EVERY_SIX_HOURS:
        return _EVERY_SIX_HOURS_CRON
    if frequency is ScheduleFrequency.DAILY:
        return f"{minute} {hour} * * *"
    return f"{minute} {hour} * * 1"


def parse_schedule(cron: str | None) -> tuple[ScheduleFrequency, int, int] | None:
    if cron is None:
        return None
    if cron == _HOURLY_CRON:
        return (ScheduleFrequency.HOURLY, 0, 0)
    if cron == _EVERY_SIX_HOURS_CRON:
        return (ScheduleFrequency.EVERY_SIX_HOURS, 0, 0)
    if match := _WEEKLY_MONDAY_PATTERN.match(cron):
        minute, hour = int(match.group(1)), int(match.group(2))
        return (ScheduleFrequency.WEEKLY_MONDAY, hour, minute)
    if match := _DAILY_PATTERN.match(cron):
        minute, hour = int(match.group(1)), int(match.group(2))
        return (ScheduleFrequency.DAILY, hour, minute)
    return None


def _format_12h(hour: int, minute: int) -> str:
    period = "AM" if hour < 12 else "PM"
    hour_12 = hour % 12 or 12
    return f"{hour_12:02d}:{minute:02d} {period}"


def describe_schedule(cron: str | None) -> str:
    if cron is None:
        return "No hay backups automáticos configurados."

    parsed = parse_schedule(cron)
    if parsed is None:
        return "Backup automático (programación personalizada)."

    frequency, hour, minute = parsed
    if frequency is ScheduleFrequency.HOURLY:
        return "Backup automático cada hora"
    if frequency is ScheduleFrequency.EVERY_SIX_HOURS:
        return "Backup automático cada 6 horas"
    if frequency is ScheduleFrequency.DAILY:
        return f"Backup automático todos los días a las {_format_12h(hour, minute)}"
    return f"Backup automático todos los lunes a las {_format_12h(hour, minute)}"
