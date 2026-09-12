"""Casos de uso de backups: copias manuales/automáticas, restauración,
exportación/importación (PROJECT_SPEC.md, "RESPALDOS")."""

from __future__ import annotations

import importlib.metadata
from datetime import UTC, datetime
from pathlib import Path

from pos.core.database.session import dispose_engine, session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.backups.application import schedule_translator
from pos.modules.backups.application.dto import (
    BackupHistoryDTO,
    BackupJobDTO,
    BackupSummaryDTO,
    BackupVerificationDTO,
)
from pos.modules.backups.domain.enums import BackupOrigin
from pos.modules.backups.infrastructure.models import BackupHistory, BackupJob
from pos.modules.backups.infrastructure.repository import BackupRepository
from pos.modules.backups.infrastructure.sqlite_file_ops import (
    backup_database_to,
    compute_sha256,
    looks_like_pos_backup,
    read_backup_metadata,
    restore_database_from,
    sqlite_path_from_url,
    write_backup_metadata,
)
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.settings.infrastructure.models import SettingValueType

_SCHEDULE_JOB_NAME = "Backup automático"
_BACKUP_ON_CLOSE_KEY = "backup_on_close_enabled"


def _app_version() -> str:
    try:
        return importlib.metadata.version("pos-system")
    except importlib.metadata.PackageNotFoundError:
        return "desconocida"


def _parse_version(value: str) -> tuple[int, ...] | None:
    """Convierte "1.2.3" en `(1, 2, 3)` para comparar versiones sin texto
    libre; `None` si no tiene forma de versión (incluye "desconocida")."""
    parts = value.strip().split(".")
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        return None


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
        origin=history.origin,
        checksum_sha256=history.checksum_sha256,
        app_version=history.app_version,
        created_by_user_id=history.created_by_user_id,
        created_by_username=history.created_by_username,
    )


class BackupService:
    """Copias de la base de datos SQLite activa, restauración, y trabajos
    programados (el disparo periódico lo hace `BackupScheduler`, este
    servicio solo sabe ejecutar un backup dado y aplicar una restauración)."""

    def __init__(
        self, database_url: str, default_backup_dir: Path, settings: BusinessSettingsService
    ) -> None:
        self._db_path = sqlite_path_from_url(database_url)
        self._default_backup_dir = default_backup_dir
        self._settings = settings

    def list_jobs(self) -> list[BackupJobDTO]:
        with session_scope() as session:
            return [_job_dto(job) for job in BackupRepository(session).list_jobs()]

    def get_active_schedule(self) -> BackupJobDTO | None:
        """La "Programación actual" (singular) que ve el usuario en la
        pantalla de Backups: el primer trabajo activo, si existe."""
        with session_scope() as session:
            for job in BackupRepository(session).list_jobs():
                if job.is_active:
                    return _job_dto(job)
        return None

    def set_schedule(self, schedule_cron: str) -> BackupJobDTO:
        """Crea o actualiza la programación automática única (upsert) —
        el diálogo de programación no gestiona una lista de trabajos, solo
        esta "programación actual"."""
        with session_scope() as session:
            repo = BackupRepository(session)
            existing = next((job for job in repo.list_jobs() if job.is_active), None)
            if existing is not None:
                repo.update_schedule(existing, schedule_cron)
                return _job_dto(existing)
            job = repo.create_job(
                name=_SCHEDULE_JOB_NAME,
                schedule_cron=schedule_cron,
                destination_path=str(self._default_backup_dir),
            )
            return _job_dto(job)

    def describe_current_schedule(self) -> str:
        job = self.get_active_schedule()
        return schedule_translator.describe_schedule(job.schedule_cron if job else None)

    def get_backup_on_close_enabled(self) -> bool:
        return self._settings.get_bool(_BACKUP_ON_CLOSE_KEY, False)

    def set_backup_on_close_enabled(self, enabled: bool) -> None:
        self._settings.set_value(
            _BACKUP_ON_CLOSE_KEY, "true" if enabled else "false", SettingValueType.BOOLEAN
        )

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

    def get_summary(self) -> BackupSummaryDTO:
        with session_scope() as session:
            repo = BackupRepository(session)
            return BackupSummaryDTO(
                manual_count=repo.count_manual_and_imported(),
                automatic_count=repo.count_scheduled(),
                total_size_bytes=repo.sum_size_bytes(),
                last_backup_at=repo.most_recent_started_at(),
            )

    def run_manual_backup(
        self,
        destination_dir: Path | None = None,
        *,
        created_by_user_id: int | None = None,
        created_by_username: str | None = None,
    ) -> BackupHistoryDTO:
        """Backup manual sin trabajo programado asociado (PROJECT_SPEC.md:
        "Copias manuales" y "Exportación")."""
        return self._run_backup(
            backup_job_id=None,
            destination_dir=destination_dir,
            origin=BackupOrigin.MANUAL,
            created_by_user_id=created_by_user_id,
            created_by_username=created_by_username,
        )

    def run_job_backup(self, job_id: int) -> BackupHistoryDTO:
        """Ejecuta el backup de un trabajo programado; lo invoca
        `BackupScheduler` en el disparo del cron."""
        with session_scope() as session:
            job = BackupRepository(session).get_job(job_id)
            if job is None:
                raise NotFoundError(f"No existe el trabajo de backup con id={job_id}.")
            destination_dir = Path(job.destination_path)
        return self._run_backup(
            backup_job_id=job_id, destination_dir=destination_dir, origin=BackupOrigin.SCHEDULED
        )

    def _run_backup(
        self,
        *,
        backup_job_id: int | None,
        destination_dir: Path | None,
        origin: BackupOrigin,
        created_by_user_id: int | None = None,
        created_by_username: str | None = None,
    ) -> BackupHistoryDTO:
        started_at = datetime.now(UTC)
        target_dir = destination_dir or self._default_backup_dir
        file_name = f"pos_backup_{started_at:%Y%m%d_%H%M%S}.db"
        destination_file = target_dir / file_name

        with session_scope() as session:
            repo = BackupRepository(session)
            history = repo.start_history(
                backup_job_id=backup_job_id,
                started_at=started_at,
                origin=origin,
                created_by_user_id=created_by_user_id,
                created_by_username=created_by_username,
            )
            history_id = history.id

        try:
            size_bytes = backup_database_to(self._db_path, destination_file)
            app_version = _app_version()
            write_backup_metadata(
                destination_file,
                app_version=app_version,
                created_at=started_at,
                origin=origin.value,
            )
            checksum = compute_sha256(destination_file)
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
                checksum_sha256=checksum,
                app_version=app_version,
            )
            return _history_dto(completed_history)

    def import_backup_file(self, file_path: Path) -> BackupHistoryDTO:
        """Registra en el historial un backup que ya existe en disco
        (botón "Buscar backups"), sin restaurarlo — solo lo deja listo
        para que el usuario elija restaurarlo después."""
        if not file_path.exists():
            raise BusinessRuleViolationError(f"El archivo '{file_path}' no existe.")
        if not looks_like_pos_backup(file_path):
            raise BusinessRuleViolationError(
                "El archivo seleccionado no es un backup válido del sistema POS."
            )

        metadata = read_backup_metadata(file_path)
        app_version = metadata.get("app_version")
        created_at_raw = metadata.get("created_at")
        created_at: datetime | None = None
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                created_at = None
        if created_at is None:
            created_at = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)

        checksum = compute_sha256(file_path)
        size_bytes = file_path.stat().st_size

        with session_scope() as session:
            history = BackupRepository(session).add_imported(
                started_at=created_at,
                finished_at=created_at,
                file_path=str(file_path),
                size_bytes=size_bytes,
                checksum_sha256=checksum,
                app_version=app_version,
            )
            return _history_dto(history)

    def verify_backup(self, history_id: int) -> BackupVerificationDTO:
        """Verificación previa a restaurar (punto 9 del pedido): integridad
        del archivo, compatibilidad de versión y que no esté corrupto. Se
        llama tanto desde `restore` como directamente desde la UI para
        mostrar el motivo exacto antes de pedir confirmación."""
        with session_scope() as session:
            entry = BackupRepository(session).get_history(history_id)
            if entry is None:
                raise NotFoundError(f"No existe el backup con id={history_id}.")
            file_path = Path(entry.file_path) if entry.file_path else None
            stored_checksum = entry.checksum_sha256
            backup_app_version = entry.app_version

        if file_path is None or not file_path.exists():
            return BackupVerificationDTO(
                ok=False,
                reason="El archivo del backup ya no existe en la ruta registrada.",
                file_exists=False,
                is_valid_sqlite=False,
                checksum_matches=None,
                version_compatible=True,
                backup_app_version=backup_app_version,
            )

        if not looks_like_pos_backup(file_path):
            return BackupVerificationDTO(
                ok=False,
                reason="El archivo del backup está dañado o no es una base de datos válida.",
                file_exists=True,
                is_valid_sqlite=False,
                checksum_matches=None,
                version_compatible=True,
                backup_app_version=backup_app_version,
            )

        checksum_matches: bool | None = None
        if stored_checksum:
            checksum_matches = compute_sha256(file_path) == stored_checksum
            if not checksum_matches:
                return BackupVerificationDTO(
                    ok=False,
                    reason=(
                        "El archivo del backup fue modificado después de registrarse "
                        "(la verificación de integridad falló)."
                    ),
                    file_exists=True,
                    is_valid_sqlite=True,
                    checksum_matches=False,
                    version_compatible=True,
                    backup_app_version=backup_app_version,
                )

        current_version = _parse_version(_app_version())
        backup_version = _parse_version(backup_app_version) if backup_app_version else None
        version_compatible = True
        if current_version is not None and backup_version is not None:
            version_compatible = backup_version <= current_version
        if not version_compatible:
            return BackupVerificationDTO(
                ok=False,
                reason=(
                    f"Este backup fue creado con una versión más nueva del sistema "
                    f"({backup_app_version}) que la versión actual instalada "
                    f"({_app_version()}). Actualiza el sistema antes de restaurar este backup."
                ),
                file_exists=True,
                is_valid_sqlite=True,
                checksum_matches=checksum_matches,
                version_compatible=False,
                backup_app_version=backup_app_version,
            )

        return BackupVerificationDTO(
            ok=True,
            reason=None,
            file_exists=True,
            is_valid_sqlite=True,
            checksum_matches=checksum_matches,
            version_compatible=True,
            backup_app_version=backup_app_version,
        )

    def restore(self, history_id: int) -> None:
        """Restaura la base de datos activa desde el backup `history_id`,
        tras verificarlo (ver `verify_backup`) — la verificación vive acá,
        no solo en la UI, para que cualquier otro llamador quede protegido
        igual.

        Libera el pool de conexiones antes de reemplazar el archivo (ver
        `core.database.session.dispose_engine`) y vuelve a dejarlo
        utilizable — no requiere reiniciar el proceso, pero sí se
        recomienda cerrar sesión y volver a entrar para que la UI no
        conserve datos en memoria de antes de la restauración.
        """
        verification = self.verify_backup(history_id)
        if not verification.ok:
            raise BusinessRuleViolationError(verification.reason or "El backup no es válido.")

        with session_scope() as session:
            entry = BackupRepository(session).get_history(history_id)
            if entry is None or entry.file_path is None:
                raise NotFoundError(f"No existe el backup con id={history_id}.")
            backup_file = Path(entry.file_path)

        dispose_engine()
        try:
            restore_database_from(backup_file, self._db_path)
        except ValueError as error:
            raise BusinessRuleViolationError(str(error)) from error
