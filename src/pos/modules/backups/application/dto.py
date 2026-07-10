"""DTOs de lectura del módulo de backups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.backups.domain.enums import BackupStatus


@dataclass(frozen=True)
class BackupJobDTO:
    id: int
    name: str
    schedule_cron: str | None
    destination_path: str
    is_active: bool


@dataclass(frozen=True)
class BackupHistoryDTO:
    id: int
    backup_job_id: int | None
    started_at: datetime
    finished_at: datetime | None
    status: BackupStatus
    file_path: str | None
    size_bytes: int | None
    error_message: str | None
