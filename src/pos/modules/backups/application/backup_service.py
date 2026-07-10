"""Casos de uso de backups: copias manuales/automáticas, restauración,
exportación/importación (PROJECT_SPEC.md, "RESPALDOS")."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pos.core.database.session import dispose_engine, session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.backups.application.dto import BackupHistoryDTO, BackupJobDTO
from pos.modules.backups.infrastructure.models import BackupHistory, BackupJob
from pos.modules.backups.infrastructure.repository import BackupRepository
from pos.modules.backups.infrastructure.sqlite_file_ops import (
    backup_database_to,
    restore_database_from,
    sqlite_path_from_url,
)


def _job_dto(job: BackupJob) -> BackupJobDTO:
    return BackupJobDTO(
        id=job.id,
        name=job.name,
        schedule_cron=job.schedule_cron,
        destination_path=job.destination_path,
        is_active=job.is_active,
    )


def _history_dto(history: BackupHistory) -> BackupHistoryDTO:
    return BackupHistoryDTO(
        id=history.id,
        backup_job_id=history.backup_job_id,
        started_at=history.started_at,
        finished_at=history.finished_at,
        status=history.status,
        file_path=history.file_path,
        size_bytes=history.size_bytes,
        error_message=history.error_message,
    )


class BackupService:
    """Copias de la base de datos SQLite activa, restauración, y trabajos
    programados (el disparo periódico lo hace `BackupScheduler`, este
    servicio solo sabe ejecutar un backup dado y aplicar una restauración)."""

    def __init__(self, database_url: str, default_backup_dir: Path) -> None:
        self._db_path = sqlite_path_from_url(database_url)
        self._default_backup_dir = default_backup_dir

    def list_jobs(self) -> list[BackupJobDTO]:
        with session_scope() as session:
            return [_job_dto(job) for job in BackupRepository(session).list_jobs()]

    def create_job(
        self, *, name: str, schedule_cron: str | None, destination_path: str | None = None
    ) -> BackupJobDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del trabajo de backup es obligatorio.")
        with session_scope() as session:
            job = BackupRepository(session).create_job(
                name=name,
                schedule_cron=schedule_cron,
                destination_path=destination_path or str(self._default_backup_dir),
            )
            return _job_dto(job)

    def set_job_active(self, job_id: int, is_active: bool) -> None:
        with session_scope() as session:
            repo = BackupRepository(session)
            job = repo.get_job(job_id)
            if job is None:
                raise NotFoundError(f"No existe el trabajo de backup con id={job_id}.")
            repo.set_job_active(job, is_active)

    def list_history(self, limit: int = 50) -> list[BackupHistoryDTO]:
        with session_scope() as session:
            return [_history_dto(h) for h in BackupRepository(session).list_history(limit)]

    def run_manual_backup(self, destination_dir: Path | None = None) -> BackupHistoryDTO:
        """Backup manual sin trabajo programado asociado (PROJECT_SPEC.md:
        "Copias manuales" y "Exportación")."""
        return self._run_backup(backup_job_id=None, destination_dir=destination_dir)

    def run_job_backup(self, job_id: int) -> BackupHistoryDTO:
        """Ejecuta el backup de un trabajo programado; lo invoca
        `BackupScheduler` en el disparo del cron."""
        with session_scope() as session:
            job = BackupRepository(session).get_job(job_id)
            if job is None:
                raise NotFoundError(f"No existe el trabajo de backup con id={job_id}.")
            destination_dir = Path(job.destination_path)
        return self._run_backup(backup_job_id=job_id, destination_dir=destination_dir)

    def _run_backup(
        self, *, backup_job_id: int | None, destination_dir: Path | None
    ) -> BackupHistoryDTO:
        started_at = datetime.now(UTC)
        target_dir = destination_dir or self._default_backup_dir
        file_name = f"pos_backup_{started_at:%Y%m%d_%H%M%S}.db"
        destination_file = target_dir / file_name

        with session_scope() as session:
            repo = BackupRepository(session)
            history = repo.start_history(backup_job_id=backup_job_id, started_at=started_at)
            history_id = history.id

        try:
            size_bytes = backup_database_to(self._db_path, destination_file)
        except OSError as error:
            with session_scope() as session:
                repo = BackupRepository(session)
                failed_history = session.get(BackupHistory, history_id)
                assert failed_history is not None
                repo.mark_failed(
                    failed_history, finished_at=datetime.now(UTC), error_message=str(error)
                )
                return _history_dto(failed_history)

        with session_scope() as session:
            repo = BackupRepository(session)
            completed_history = session.get(BackupHistory, history_id)
            assert completed_history is not None
            repo.mark_success(
                completed_history,
                finished_at=datetime.now(UTC),
                file_path=str(destination_file),
                size_bytes=size_bytes,
            )
            return _history_dto(completed_history)

    def restore(self, backup_file: Path) -> None:
        """Restaura la base de datos activa desde `backup_file`.

        Libera el pool de conexiones antes de reemplazar el archivo (ver
        `core.database.session.dispose_engine`) y vuelve a dejarlo
        utilizable — no requiere reiniciar el proceso, pero sí se
        recomienda cerrar sesión y volver a entrar para que la UI no
        conserve datos en memoria de antes de la restauración.
        """
        dispose_engine()
        try:
            restore_database_from(backup_file, self._db_path)
        except ValueError as error:
            raise BusinessRuleViolationError(str(error)) from error
