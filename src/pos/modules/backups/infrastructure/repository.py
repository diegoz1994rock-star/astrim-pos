"""Acceso a datos de trabajos de backup y su historial de ejecución."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.backups.domain.enums import BackupOrigin, BackupStatus
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

    def update_schedule(self, job: BackupJob, schedule_cron: str) -> None:
        job.schedule_cron = schedule_cron

    def start_history(
        self,
        *,
        backup_job_id: int | None,
        started_at: datetime,
        origin: BackupOrigin,
        created_by_user_id: int | None = None,
        created_by_username: str | None = None,
    ) -> BackupHistory:
        history = BackupHistory(
            backup_job_id=backup_job_id,
            started_at=started_at,
            status=BackupStatus.IN_PROGRESS,
            origin=origin,
            created_by_user_id=created_by_user_id,
            created_by_username=created_by_username,
        )
        self._session.add(history)
        self._session.flush()
        return history

    def mark_success(
        self,
        history: BackupHistory,
        *,
        finished_at: datetime,
        file_path: str,
        size_bytes: int,
        checksum_sha256: str | None = None,
        app_version: str | None = None,
    ) -> None:
        history.status = BackupStatus.SUCCESS
        history.finished_at = finished_at
        history.file_path = file_path
        history.size_bytes = size_bytes
        history.checksum_sha256 = checksum_sha256
        history.app_version = app_version

    def mark_failed(
        self, history: BackupHistory, *, finished_at: datetime, error_message: str
    ) -> None:
        history.status = BackupStatus.FAILED
        history.finished_at = finished_at
        history.error_message = error_message

    def add_imported(
        self,
        *,
        started_at: datetime,
        finished_at: datetime,
        file_path: str,
        size_bytes: int,
        checksum_sha256: str,
        app_version: str | None,
    ) -> BackupHistory:
        history = BackupHistory(
            backup_job_id=None,
            started_at=started_at,
            finished_at=finished_at,
            status=BackupStatus.SUCCESS,
            file_path=file_path,
            size_bytes=size_bytes,
            origin=BackupOrigin.IMPORTED,
            checksum_sha256=checksum_sha256,
            app_version=app_version,
        )
        self._session.add(history)
        self._session.flush()
        return history

    def get_history(self, history_id: int) -> BackupHistory | None:
        return self._session.get(BackupHistory, history_id)

    def list_history(self, limit: int = 50) -> list[BackupHistory]:
        return list(
            self._session.scalars(
                select(BackupHistory).order_by(BackupHistory.started_at.desc()).limit(limit)
            )
        )

    def count_manual_and_imported(self) -> int:
        return (
            self._session.scalar(
                select(func.count(BackupHistory.id)).where(
                    BackupHistory.origin.in_([BackupOrigin.MANUAL, BackupOrigin.IMPORTED]),
                    BackupHistory.status == BackupStatus.SUCCESS,
                )
            )
            or 0
        )

    def count_scheduled(self) -> int:
        return (
            self._session.scalar(
                select(func.count(BackupHistory.id)).where(
                    BackupHistory.origin == BackupOrigin.SCHEDULED,
                    BackupHistory.status == BackupStatus.SUCCESS,
                )
            )
            or 0
        )

    def sum_size_bytes(self) -> int:
        return (
            self._session.scalar(
                select(func.coalesce(func.sum(BackupHistory.size_bytes), 0)).where(
                    BackupHistory.status == BackupStatus.SUCCESS
                )
            )
            or 0
        )

    def most_recent_started_at(self) -> datetime | None:
        return self._session.scalar(
            select(func.max(BackupHistory.started_at)).where(
                BackupHistory.status == BackupStatus.SUCCESS
            )
        )
