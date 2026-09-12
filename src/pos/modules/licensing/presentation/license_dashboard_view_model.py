"""View model del panel de administración de Licencia (dashboard) —
distinto de `LicenseViewModel` (ese sigue usándose solo para la pantalla
de bloqueo pre-login, sin cambios). Refresca periódicamente (mismo patrón
que `SyncViewModel`) porque no existe hoy un canal de notificación en
tiempo real real — ver `domain/events.py` para el mecanismo de
sincronización futura."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.licensing.application.license_service import LicenseService

_REFRESH_INTERVAL_MS = 45_000


class LicenseDashboardViewModel(QObject):
    verification_changed = Signal(object)
    """Emite `LicenseVerificationDTO`."""
    devices_loaded = Signal(list)
    """Emite `list[AuthorizedDeviceDTO]`."""
    history_loaded = Signal(list)
    """Emite `list[LicenseHistoryEntryDTO]`."""
    usage_loaded = Signal(object)
    """Emite `LicenseUsageDTO | None`."""
    connectivity_changed = Signal(bool)
    """`True` si el último ciclo de refresco local corrió sin errores —
    no existe un servidor central real que consultar, así que esto es lo
    más honesto que puede representar un indicador "en línea/fuera de
    línea" hoy (ver plan de este módulo, sección de caveats)."""
    error_occurred = Signal(str)
    info_occurred = Signal(str)

    def __init__(
        self,
        license_service: LicenseService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._license_service = license_service
        self._session_manager = session_manager
        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._refresh)

    @property
    def hardware_fingerprint(self) -> str:
        from pos.modules.licensing.infrastructure.hardware import get_hardware_fingerprint

        return get_hardware_fingerprint()

    def start_refreshing(self) -> None:
        self._refresh()
        self._timer.start()

    def stop_refreshing(self) -> None:
        self._timer.stop()

    def refresh_now(self) -> None:
        self._refresh()

    # -- acciones ---------------------------------------------------------

    def activate(self, code: str) -> None:
        code = code.strip()
        if not code:
            self.error_occurred.emit(
                "Pega el código de licencia (ej. XXXX-XXXX-ASTR-XXXX-XXXX-XXXX-XXXX)."
            )
            return
        self._run(
            lambda: self._license_service.activate(code, activated_by=self._activated_by()),
            "Licencia activada.",
        )

    def renew(self, code: str) -> None:
        code = code.strip()
        if not code:
            self.error_occurred.emit(
                "Pega el nuevo código de licencia (ej. XXXX-XXXX-ASTR-XXXX-XXXX-XXXX-XXXX)."
            )
            return
        self._run(
            lambda: self._license_service.renew(code, activated_by=self._activated_by()),
            "Licencia renovada.",
        )

    def _activated_by(self) -> str | None:
        session = self._session_manager.current
        return session.full_name if session is not None else None

    def suspend(self, reason: str | None = None) -> None:
        self._run(lambda: self._license_service.suspend(reason), "Licencia suspendida.")

    def reactivate(self) -> None:
        self._run(lambda: self._license_service.reactivate(), "Licencia reactivada.")

    def block(self, reason: str | None = None) -> None:
        self._run(lambda: self._license_service.block(reason), "Licencia bloqueada.")

    def revoke_device(self, hardware_fingerprint: str) -> None:
        self._run(
            lambda: self._license_service.revoke_device(hardware_fingerprint),
            "Dispositivo revocado.",
        )

    def _run(self, action, success_message: str) -> None:
        try:
            action()
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self.info_occurred.emit(success_message)
        self._refresh()

    # -- refresco -----------------------------------------------------------

    def _refresh(self) -> None:
        try:
            verification = self._license_service.verify()
            devices = self._license_service.get_authorized_devices()
            history = self._license_service.get_history()
            usage = self._license_service.get_usage_summary()
        except Exception:
            self.connectivity_changed.emit(False)
            return
        self.connectivity_changed.emit(True)
        self.verification_changed.emit(verification)
        self.devices_loaded.emit(devices)
        self.history_loaded.emit(history)
        self.usage_loaded.emit(usage)
