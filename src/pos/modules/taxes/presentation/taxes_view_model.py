"""View model de administración de impuestos."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.taxes.application.tax_service import TaxService


class TaxesViewModel(QObject):
    taxes_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, service: TaxService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def load(self) -> None:
        self.taxes_loaded.emit(self._service.list_taxes())

    def create_tax(self, name: str, rate_percent: Decimal) -> None:
        try:
            self._service.create_tax(name=name, rate_percent=rate_percent)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Impuesto '{name}' creado.")
            self.load()

    def update_tax(self, tax_id: int, name: str, rate_percent: Decimal) -> None:
        try:
            self._service.update_tax(tax_id, name=name, rate_percent=rate_percent)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Impuesto '{name}' actualizado.")
            self.load()

    def set_active(self, tax_id: int, is_active: bool) -> None:
        try:
            self._service.set_active(tax_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def delete_tax(self, tax_id: int) -> None:
        try:
            self._service.delete_tax(tax_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Impuesto eliminado correctamente.")
            self.load()
