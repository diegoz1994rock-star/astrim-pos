"""Acceso a datos de trabajos de backup y su historial de ejecución."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.backups.domain.enums import BackupStatus
from pos.modules.backups.infrastructure.models import BackupHistory, BackupJob


class BackupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_jobs(self) -> list[BackupJob]:
        return list(self._session.scalars(select(BackupJob).order_by(BackupJob.name)))

    def get_job(self, job_id: int) -> BackupJob | None:
        return self._session.get(BackupJob, job_id)

    def create_job(
        self, *, name: str, schedule_cron: str | None, destination_path: str
    ) -> BackupJob:
        job = BackupJob(
            name=name,
            schedule_cron=schedule_cron,
            destination_path=destination_path,
            is_active=True,
        )
        self._session.add(job)
        self._session.flush()
        return job

    def set_job_active(self, job: BackupJob, is_active: bool) -> None:
        job.is_active = is_active

    def start_history(self, *, backup_job_id: int | None, started_at: datetime) -> BackupHistory:
        history = BackupHistory(
            backup_job_id=backup_job_id, started_at=started_at, status=BackupStatus.IN_PROGRESS
        )
        self._session.add(history)
        self._session.flush()
        return history

    def mark_success(
        self, history: BackupHistory, *, finished_at: datetime, file_path: str, size_bytes: int
    ) -> None:
        history.status = BackupStatus.SUCCESS
        history.finished_at = finished_at
        history.file_path = file_path
        history.size_bytes = size_bytes

    def mark_failed(
        self, history: BackupHistory, *, finished_at: datetime, error_message: str
    ) -> None:
        history.status = BackupStatus.FAILED
        history.finished_at = finished_at
        history.error_message = error_message

    def list_history(self, limit: int = 50) -> list[BackupHistory]:
        return list(
            self._session.scalars(
                select(BackupHistory).order_by(BackupHistory.started_at.desc()).limit(limit)
            )
        )
