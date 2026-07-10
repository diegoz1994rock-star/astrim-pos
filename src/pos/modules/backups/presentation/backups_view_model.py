"""View model de la pantalla de backups."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.backups.application.backup_service import BackupService


class BackupsViewModel(QObject):
    jobs_loaded = Signal(list)
    history_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, backup_service: BackupService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backup_service = backup_service

    def load(self) -> None:
        self.jobs_loaded.emit(self._backup_service.list_jobs())
        self.history_loaded.emit(self._backup_service.list_history())

    def run_manual_backup(self, destination_dir: Path | None) -> None:
        try:
            history = self._backup_service.run_manual_backup(destination_dir)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        if history.status.value == "failed":
            self.error_occurred.emit(history.error_message or "El backup falló.")
        else:
            self.operation_succeeded.emit(f"Backup creado: {history.file_path}")
        self.load()

    def create_job(self, name: str, cron_expression: str, destination_dir: str) -> None:
        try:
            self._backup_service.create_job(
                name=name,
                schedule_cron=cron_expression or None,
                destination_path=destination_dir or None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Trabajo de backup creado.")
            self.load()

    def restore(self, backup_file: Path) -> None:
        try:
            self._backup_service.restore(backup_file)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(
                "Base de datos restaurada. Cierra sesión y vuelve a entrar para "
                "asegurarte de ver los datos restaurados."
            )
