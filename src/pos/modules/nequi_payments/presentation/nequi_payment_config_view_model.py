"""View model de administración de números de Nequi."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService


class NequiPaymentConfigViewModel(QObject):
    configs_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, service: NequiPaymentService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def load(self) -> None:
        self.configs_loaded.emit(self._service.list_configs())

    def create_config(self, number: str) -> None:
        try:
            self._service.create_config(number=number)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Número de Nequi '{number}' creado.")
            self.load()

    def update_config(self, config_id: int, number: str) -> None:
        try:
            self._service.update_config(config_id, number=number)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Número de Nequi '{number}' actualizado.")
            self.load()

    def set_active(self, config_id: int, is_active: bool) -> None:
        try:
            self._service.set_active(config_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def set_default(self, config_id: int) -> None:
        try:
            self._service.set_default(config_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Número de Nequi predeterminado actualizado.")
            self.load()

    def delete_config(self, config_id: int) -> None:
        try:
            self._service.delete_config(config_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Número de Nequi eliminado.")
            self.load()
