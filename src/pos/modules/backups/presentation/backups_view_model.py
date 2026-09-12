"""View model de la pantalla de backups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.backups.application import schedule_translator
from pos.modules.backups.application.backup_service import BackupService
from pos.modules.backups.application.dto import BackupVerificationDTO
from pos.modules.backups.application.scheduler import BackupScheduler
from pos.modules.backups.domain.enums import ScheduleFrequency

_DEFAULT_HOUR = 2
_DEFAULT_MINUTE = 0
_HISTORY_LIMIT = 5000


@dataclass(frozen=True)
class BackupsSummaryDisplay:
    """Combina el agregado del servicio (`BackupSummaryDTO`) con la
    "próxima ejecución" del scheduler — dos fuentes distintas que solo el
    view model conoce a la vez, igual que se hizo con el cierre de caja de
    Ventas (composición de presentación, no domain)."""

    manual_count: int
    automatic_count: int
    total_size_bytes: int
    last_backup_at: datetime | None
    next_scheduled_at: datetime | None


class BackupsViewModel(QObject):
    schedule_loaded = Signal(str)
    history_loaded = Signal(list)
    summary_loaded = Signal(object)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        backup_service: BackupService,
        backup_scheduler: BackupScheduler,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backup_service = backup_service
        self._backup_scheduler = backup_scheduler
        self._session_manager = session_manager

    def load(self) -> None:
        self.schedule_loaded.emit(self._backup_service.describe_current_schedule())
        self.history_loaded.emit(self._backup_service.list_history(limit=_HISTORY_LIMIT))
        self.summary_loaded.emit(self._build_summary())

    def _build_summary(self) -> BackupsSummaryDisplay:
        summary = self._backup_service.get_summary()
        next_scheduled_at: datetime | None = None
        active_job = self._backup_service.get_active_schedule()
        if active_job is not None:
            next_scheduled_at = self._backup_scheduler.get_next_run_time(active_job.id)
        return BackupsSummaryDisplay(
            manual_count=summary.manual_count,
            automatic_count=summary.automatic_count,
            total_size_bytes=summary.total_size_bytes,
            last_backup_at=summary.last_backup_at,
            next_scheduled_at=next_scheduled_at,
        )

    def current_schedule_state(self) -> tuple[ScheduleFrequency, int, int, bool]:
        """Estado para precargar el diálogo de programación: si no hay una
        programación reconocible todavía, se ofrece un horario por defecto
        razonable (diario a las 02:00) en vez de dejarlo sin seleccionar."""
        job = self._backup_service.get_active_schedule()
        parsed = schedule_translator.parse_schedule(job.schedule_cron if job else None)
        default = (ScheduleFrequency.DAILY, _DEFAULT_HOUR, _DEFAULT_MINUTE)
        frequency, hour, minute = parsed or default
        backup_on_close = self._backup_service.get_backup_on_close_enabled()
        return frequency, hour, minute, backup_on_close

    def save_schedule(
        self, frequency: ScheduleFrequency, hour: int, minute: int, backup_on_close: bool
    ) -> None:
        cron_expression = schedule_translator.build_cron(frequency, hour, minute)
        try:
            job = self._backup_service.set_schedule(cron_expression)
            self._backup_service.set_backup_on_close_enabled(backup_on_close)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self._backup_scheduler.reschedule_job(job.id, cron_expression)
        self.operation_succeeded.emit("Programación de backups guardada.")
        self.load()

    def run_manual_backup(self, destination_dir: Path | None) -> None:
        session = self._session_manager.current
        try:
            history = self._backup_service.run_manual_backup(
                destination_dir,
                created_by_user_id=session.user_id if session else None,
                created_by_username=session.full_name if session else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        if history.status.value == "failed":
            self.error_occurred.emit(history.error_message or "El backup falló.")
        else:
            self.operation_succeeded.emit(f"Backup creado: {history.file_path}")
        self.load()

    def import_backup_file(self, file_path: Path) -> None:
        try:
            history = self._backup_service.import_backup_file(file_path)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self.operation_succeeded.emit(
            f"Backup registrado: {history.file_path}\n"
            f"Fecha: {history.started_at:%Y-%m-%d %H:%M} — "
            f"Versión: {history.app_version or 'Desconocida'}\n"
            "Queda listo para restaurar; no se restauró automáticamente."
        )
        self.load()

    def verify_backup(self, history_id: int) -> BackupVerificationDTO | None:
        try:
            return self._backup_service.verify_backup(history_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return None

    def restore(self, history_id: int) -> None:
        try:
            self._backup_service.restore(history_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(
                "Base de datos restaurada. Cierra sesión y vuelve a entrar para "
                "asegurarte de ver los datos restaurados."
            )
            self.load()
