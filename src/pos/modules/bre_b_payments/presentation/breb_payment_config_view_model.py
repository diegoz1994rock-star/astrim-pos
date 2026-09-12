"""View model de administración de llaves Bre-B."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService


class BreBPaymentConfigViewModel(QObject):
    configs_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, service: BreBPaymentService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def load(self) -> None:
        self.configs_loaded.emit(self._service.list_configs())

    def create_config(self, key: str) -> None:
        try:
            self._service.create_config(key=key)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Llave Bre-B '{key}' creada.")
            self.load()

    def update_config(self, config_id: int, key: str) -> None:
        try:
            self._service.update_config(config_id, key=key)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Llave Bre-B '{key}' actualizada.")
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
            self.operation_succeeded.emit("Llave Bre-B predeterminada actualizada.")
            self.load()

    def delete_config(self, config_id: int) -> None:
        try:
            self._service.delete_config(config_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Llave Bre-B eliminada.")
            self.load()
