"""Modelos SQLAlchemy de backups: trabajos programados e historial de ejecuciones."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.backups.domain.enums import BackupOrigin, BackupStatus


class BackupJob(Base, TimestampMixin):
    """Trabajo de backup programado (PROJECT_SPEC.md, "RESPALDOS").

    `schedule_cron` es nulo para backups puramente manuales, que se
    disparan bajo demanda sin un `BackupJob` asociado en `BackupHistory`.
    """

    __tablename__ = "backup_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(50), nullable=True)
    destination_path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BackupHistory(Base):
    """Ejecución concreta de un backup, manual o programado."""

    __tablename__ = "backup_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    backup_job_id: Mapped[int | None] = mapped_column(ForeignKey("backup_jobs.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[BackupStatus] = mapped_column(
        Enum(BackupStatus, native_enum=False), default=BackupStatus.IN_PROGRESS, nullable=False
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[BackupOrigin] = mapped_column(
        Enum(BackupOrigin, native_enum=False), default=BackupOrigin.MANUAL, nullable=False
    )
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
