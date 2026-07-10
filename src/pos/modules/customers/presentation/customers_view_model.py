"""View model de administración de clientes."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.infrastructure.models import CreditMovementType


class CustomersViewModel(QObject):
    customers_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self, customer_service: CustomerManagementService, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._customer_service = customer_service

    def load(self) -> None:
        self.customers_loaded.emit(self._customer_service.list_customers())

    def create_customer(self, **kwargs: object) -> None:
        try:
            self._customer_service.create_customer(**kwargs)  # type: ignore[arg-type]
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Cliente creado correctamente.")
            self.load()

    def remove_customer(self, customer_id: int) -> None:
        try:
            self._customer_service.remove_customer(customer_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def register_credit_movement(
        self, customer_id: int, movement_type: CreditMovementType, amount: Decimal
    ) -> None:
        try:
            self._customer_service.register_credit_movement(
                customer_id=customer_id, movement_type=movement_type, amount=amount
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Movimiento de crédito registrado.")
            self.load()
