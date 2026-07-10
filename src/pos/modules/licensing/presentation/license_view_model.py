"""View model de la pantalla de licencia (activación y estado)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.licensing.application.dto import LicenseVerificationDTO
from pos.modules.licensing.application.license_service import LicenseService
from pos.modules.licensing.infrastructure.hardware import get_hardware_fingerprint


class LicenseViewModel(QObject):
    status_changed = Signal(object)
    """Emite `LicenseVerificationDTO` con el estado actual."""
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, license_service: LicenseService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._license_service = license_service

    @property
    def hardware_fingerprint(self) -> str:
        return get_hardware_fingerprint()

    def refresh(self) -> LicenseVerificationDTO:
        verification = self._license_service.verify()
        self.status_changed.emit(verification)
        return verification

    def activate(self, license_key: str) -> None:
        license_key = license_key.strip()
        if not license_key:
            self.error_occurred.emit("Pega la clave de licencia que te dio el proveedor.")
            return
        try:
            self._license_service.activate(license_key)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Licencia activada correctamente.")
            self.refresh()
