"""DTOs de lectura del módulo de backups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.backups.domain.enums import BackupOrigin, BackupStatus


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
    origin: BackupOrigin
    checksum_sha256: str | None
    app_version: str | None
    created_by_user_id: int | None
    created_by_username: str | None


@dataclass(frozen=True)
class BackupVerificationDTO:
    """Resultado de verificar un backup antes de restaurarlo
    (`BackupService.verify_backup`) — `reason` viene siempre lleno cuando
    `ok` es falso, con el motivo exacto para mostrar al usuario."""

    ok: bool
    reason: str | None
    file_exists: bool
    is_valid_sqlite: bool
    checksum_matches: bool | None
    """`None` cuando la entrada no tiene un checksum guardado con el que
    comparar (backups registrados antes de esta funcionalidad)."""
    version_compatible: bool
    backup_app_version: str | None


@dataclass(frozen=True)
class BackupSummaryDTO:
    manual_count: int
    automatic_count: int
    total_size_bytes: int
    last_backup_at: datetime | None
