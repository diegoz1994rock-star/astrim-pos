"""View model de administración de Cajón monedero."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_drawers.domain.enums import CashDrawerOpeningKind
from pos.modules.cash_register.application.cash_register_service import CashRegisterService


class CashDrawersViewModel(QObject):
    devices_loaded = Signal(list)
    cash_registers_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        service: CashDrawerService,
        cash_register_service: CashRegisterService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._cash_register_service = cash_register_service
        self._session_manager = session_manager

    @property
    def service(self) -> CashDrawerService:
        return self._service

    @property
    def session_manager(self) -> SessionManager:
        """Expuesto para el panel de pruebas, que necesita el usuario
        autenticado para probar la apertura (nunca aperturas anónimas)."""
        return self._session_manager

    def load(self) -> None:
        self.devices_loaded.emit(self._service.list_devices())
        self.cash_registers_loaded.emit(
            [(r.id, r.name) for r in self._cash_register_service.list_registers()]
        )

    def create_device(self, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.create_device(**fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Cajón '{name}' creado.")
            self.load()

    def update_device(self, device_id: int, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.update_device(device_id, **fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Cajón '{name}' actualizado.")
            self.load()

    def set_active(self, device_id: int, is_active: bool) -> None:
        try:
            self._service.set_device_active(device_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def set_default(self, device_id: int) -> None:
        try:
            self._service.set_default_device(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Cajón marcado como predeterminado.")
            self.load()

    def delete_device(self, device_id: int) -> None:
        try:
            self._service.delete_device(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Cajón eliminado correctamente.")
            self.load()

    def test_connection(self, device_id: int) -> None:
        try:
            ok = self._service.test_connection(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            if ok:
                self.operation_succeeded.emit("Conexión exitosa con el cajón.")
            else:
                self.error_occurred.emit("No se pudo conectar con el cajón.")

    def connect_device(self, device_id: int) -> None:
        try:
            self._service.connect(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Cajón conectado.")
        self.load()

    def disconnect_device(self, device_id: int) -> None:
        try:
            self._service.disconnect(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Cajón desconectado.")
        self.load()

    def open_drawer(self, device_id: int, reason: str) -> None:
        """Apertura manual — exige un usuario autenticado (nunca aperturas
        anónimas) y un motivo, ambos quedan en el historial de auditoría
        junto con la fecha/hora/caja."""
        current_user = self._session_manager.current
        if current_user is None:
            self.error_occurred.emit("Debes iniciar sesión para abrir el cajón manualmente.")
            return
        try:
            self._service.open_drawer(
                device_id,
                user_id=current_user.user_id,
                username=current_user.username,
                opening_kind=CashDrawerOpeningKind.MANUAL,
                reason=reason,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Apertura enviada.")
