"""View model de la pantalla de Auditoría (solo lectura)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.modules.sync.application.audit_formatter import format_audit_entry
from pos.modules.sync.application.dto import SyncLogEntryDTO
from pos.modules.sync.application.sync_service import SyncService


class AuditLogViewModel(QObject):
    entries_loaded = Signal(list)
    """Emite una lista de tuplas `(SyncLogEntryDTO, descripción_legible)`."""

    def __init__(self, sync_service: SyncService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sync_service = sync_service

    def load(self, limit: int = 200) -> None:
        entries: list[SyncLogEntryDTO] = self._sync_service.list_recent(limit)
        self.entries_loaded.emit([(entry, format_audit_entry(entry)) for entry in entries])
