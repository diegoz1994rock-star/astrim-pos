"""View model de Administración → Configuración de factura."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)


class InvoiceSettingsViewModel(QObject):
    settings_loaded = Signal(object)
    """Emite `InvoiceSettingsDTO`."""
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, service: InvoiceSettingsService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def load(self) -> None:
        self.settings_loaded.emit(self._service.get_settings())

    def save(self, settings: InvoiceSettingsDTO) -> None:
        try:
            saved = self._service.update_settings(settings)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Configuración de factura guardada.")
            self.settings_loaded.emit(saved)
