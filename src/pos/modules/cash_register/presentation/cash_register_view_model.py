"""View model de la pantalla de caja."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.cash_register.domain.enums import CashMovementType


class CashRegisterViewModel(QObject):
    registers_loaded = Signal(list)
    session_changed = Signal(object)
    """Emite `CashSessionDTO | None`: la sesión abierta del punto de caja
    seleccionado, o `None` si no hay ninguna."""
    movements_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        cash_register_service: CashRegisterService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = cash_register_service
        self._session_manager = session_manager
        self._selected_register_id: int | None = None

    def load(self) -> None:
        self.registers_loaded.emit(self._service.list_registers())

    def select_register(self, register_id: int) -> None:
        self._selected_register_id = register_id
        self._refresh_session()

    def _refresh_session(self) -> None:
        if self._selected_register_id is None:
            return
        cash_session = self._service.get_open_session(self._selected_register_id)
        self.session_changed.emit(cash_session)
        if cash_session is not None:
            self.movements_loaded.emit(self._service.list_movements(cash_session.id))
        else:
            self.movements_loaded.emit([])

    def _current_user_id(self) -> int | None:
        current = self._session_manager.current
        return current.user_id if current is not None else None

    def open_session(self, opening_amount: Decimal) -> None:
        if self._selected_register_id is None:
            self.error_occurred.emit("Selecciona un punto de caja.")
            return
        try:
            self._service.open_session(
                cash_register_id=self._selected_register_id,
                opened_by_user_id=self._current_user_id() or 0,
                opening_amount=opening_amount,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Turno de caja abierto.")
            self._refresh_session()

    def register_movement(
        self, movement_type: CashMovementType, amount: Decimal, reason: str
    ) -> None:
        cash_session = self._service.get_open_session(self._selected_register_id or -1)
        if cash_session is None:
            self.error_occurred.emit("No hay un turno de caja abierto.")
            return
        try:
            self._service.register_manual_movement(
                cash_session_id=cash_session.id,
                movement_type=movement_type,
                amount=amount,
                reason=reason or None,
                created_by_user_id=self._current_user_id(),
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Movimiento registrado.")
            self._refresh_session()

    def close_session(self, counted_amount: Decimal) -> None:
        cash_session = self._service.get_open_session(self._selected_register_id or -1)
        if cash_session is None:
            self.error_occurred.emit("No hay un turno de caja abierto.")
            return
        try:
            closed = self._service.close_session(
                cash_session_id=cash_session.id,
                closed_by_user_id=self._current_user_id() or 0,
                counted_amount=counted_amount,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(
                f"Turno cerrado. Diferencia: {closed.difference}"
            )
            self._refresh_session()
