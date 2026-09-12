"""Enumeraciones de dominio del módulo de backups."""

from __future__ import annotations

import enum


class BackupStatus(enum.Enum):
    """Estado de una ejecución de backup."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class ScheduleFrequency(enum.Enum):
    """Frecuencias de backup automático ofrecidas al usuario — nunca se le
    muestra la expresión cron subyacente (ver `application/schedule_translator.py`)."""

    HOURLY = "hourly"
    EVERY_SIX_HOURS = "every_six_hours"
    DAILY = "daily"
    WEEKLY_MONDAY = "weekly_monday"


class BackupOrigin(enum.Enum):
    """Cómo se originó una entrada de `BackupHistory`. Sustituye la
    derivación ambigua "`backup_job_id is None` = manual" — un backup
    registrado con "Buscar backups" (`BackupService.import_backup_file`)
    tampoco tiene `backup_job_id`, pero no es lo mismo que uno creado
    manualmente desde esta instalación."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    IMPORTED = "imported"
