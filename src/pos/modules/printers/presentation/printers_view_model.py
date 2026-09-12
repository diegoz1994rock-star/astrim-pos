"""View model de administración de Impresoras (Administración → Dispositivos
→ Impresoras)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.printers.application.printer_service import PrinterService


class PrintersViewModel(QObject):
    devices_loaded = Signal(list)
    cash_registers_loaded = Signal(list)
    detected_printers_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        service: PrinterService,
        cash_register_service: CashRegisterService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._cash_register_service = cash_register_service
        self._session_manager = session_manager

    @property
    def service(self) -> PrinterService:
        return self._service

    @property
    def session_manager(self) -> SessionManager:
        """Expuesto para el panel de pruebas, que necesita el usuario
        autenticado para imprimir una página de prueba (nunca impresiones
        anónimas)."""
        return self._session_manager

    def load(self) -> None:
        self.devices_loaded.emit(self._service.list_devices())
        self.cash_registers_loaded.emit(
            [(r.id, r.name) for r in self._cash_register_service.list_registers()]
        )

    def discover_printers(self) -> None:
        try:
            detected = self._service.discover_printers()
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.detected_printers_loaded.emit(detected)

    def create_device(self, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.create_device(**fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Impresora '{name}' creada.")
            self.load()

    def update_device(self, device_id: int, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.update_device(device_id, **fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Impresora '{name}' actualizada.")
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
            self.operation_succeeded.emit("Impresora marcada como predeterminada.")
            self.load()

    def delete_device(self, device_id: int) -> None:
        try:
            self._service.delete_device(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Impresora eliminada correctamente.")
            self.load()

    def test_connection(self, device_id: int) -> None:
        try:
            ok = self._service.test_connection(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            if ok:
                self.operation_succeeded.emit("Conexión exitosa con la impresora.")
            else:
                self.error_occurred.emit("No se pudo conectar con la impresora.")

    def connect_device(self, device_id: int) -> None:
        try:
            self._service.connect(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Impresora conectada.")
        self.load()

    def disconnect_device(self, device_id: int) -> None:
        try:
            self._service.disconnect(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Impresora desconectada.")
        self.load()
