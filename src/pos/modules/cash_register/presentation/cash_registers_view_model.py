"""View model de administración de cajas registradoras (puntos de cobro)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService


class CashRegistersViewModel(QObject):
    registers_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, service: CashRegisterService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def load(self) -> None:
        self.registers_loaded.emit(self._service.list_all_registers())

    def create_register(self, name: str, location: str | None) -> None:
        try:
            self._service.create_register(name=name, location=location)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Caja '{name}' creada.")
            self.load()

    def update_register(self, register_id: int, name: str, location: str | None) -> None:
        try:
            self._service.update_register(register_id, name=name, location=location)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Caja '{name}' actualizada.")
            self.load()

    def set_active(self, register_id: int, is_active: bool) -> None:
        try:
            self._service.set_register_active(register_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def delete_register(self, register_id: int) -> None:
        try:
            self._service.delete_register(register_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Caja eliminada correctamente.")
            self.load()
