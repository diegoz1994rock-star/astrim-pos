"""Enumeraciones de dominio del módulo de backups."""

from __future__ import annotations

import enum


class BackupStatus(enum.Enum):
    """Estado de una ejecución de backup."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
