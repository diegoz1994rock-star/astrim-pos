"""Casos de uso de caja: apertura, cierre, arqueo y movimientos manuales."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.cash_register.application.dto import (
    CashMovementDTO,
    CashRegisterDTO,
    CashSessionDTO,
)
from pos.modules.cash_register.domain.enums import CashMovementType, CashSessionStatus
from pos.modules.cash_register.domain.events import CashSessionClosedEvent, CashSessionOpenedEvent
from pos.modules.cash_register.infrastructure.models import CashRegister, CashSession
from pos.modules.cash_register.infrastructure.repository import CashRegisterRepository

_INFLOW_TYPES = (CashMovementType.SALE, CashMovementType.MANUAL_IN)
_OUTFLOW_TYPES = (CashMovementType.MANUAL_OUT, CashMovementType.REFUND)


def _register_dto(register: CashRegister) -> CashRegisterDTO:
    return CashRegisterDTO(
        id=register.id, name=register.name, location=register.location, is_active=register.is_active
    )


def _session_dto(cash_session: CashSession, register_name: str) -> CashSessionDTO:
    return CashSessionDTO(
        id=cash_session.id,
        cash_register_id=cash_session.cash_register_id,
        cash_register_name=register_name,
        status=cash_session.status,
        opened_by_user_id=cash_session.opened_by_user_id,
        opened_at=cash_session.opened_at,
        opening_amount=cash_session.opening_amount,
        closed_at=cash_session.closed_at,
        closing_amount=cash_session.closing_amount,
        expected_amount=cash_session.expected_amount,
        difference=cash_session.difference,
    )


class CashRegisterService:
    """Apertura/cierre de turnos de caja, movimientos manuales y arqueo."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_registers(self) -> list[CashRegisterDTO]:
        with session_scope() as session:
            repo = CashRegisterRepository(session)
            return [_register_dto(r) for r in repo.list_registers()]

    def create_register(self, *, name: str, location: str | None = None) -> CashRegisterDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del punto de caja es obligatorio.")
        with session_scope() as session:
            repo = CashRegisterRepository(session)
            return _register_dto(repo.create_register(name=name, location=location))

    def get_open_session(self, register_id: int) -> CashSessionDTO | None:
        with session_scope() as session:
            repo = CashRegisterRepository(session)
            cash_session = repo.get_open_session(register_id)
            if cash_session is None:
                return None
            register = repo.get_register(register_id)
            assert register is not None
            return _session_dto(cash_session, register.name)

    def require_open_session(self, cash_session_id: int) -> None:
        """Valida que `cash_session_id` exista y esté abierta.

        Usado por Ventas para verificar la sesión de caja *antes* de
        completar una venta, incluso cuando la venta no tiene componente en
        efectivo (crédito/tarjeta 100%) — de lo contrario esa validación
        solo ocurriría por accidente cuando `register_sale_movement` se
        invoca, y nunca para ventas sin efectivo.
        """
        with session_scope() as session:
            repo = CashRegisterRepository(session)
            cash_session = repo.get_session(cash_session_id)
            if cash_session is None:
                raise NotFoundError(f"No existe la sesión de caja con id={cash_session_id}.")
            if cash_session.status is not CashSessionStatus.OPEN:
                raise BusinessRuleViolationError(
                    "No se puede completar la venta: la sesión de caja no está abierta."
                )

    def open_session(
        self, *, cash_register_id: int, opened_by_user_id: int, opening_amount: Decimal
    ) -> CashSessionDTO:
        if opening_amount < 0:
            raise BusinessRuleViolationError("El monto de apertura no puede ser negativo.")

        with session_scope() as session:
            repo = CashRegisterRepository(session)
            register = repo.get_register(cash_register_id)
            if register is None:
                raise NotFoundError(f"No existe el punto de caja con id={cash_register_id}.")
            if repo.get_open_session(cash_register_id) is not None:
                raise BusinessRuleViolationError(
                    f"El punto de caja '{register.name}' ya tiene un turno abierto."
                )

            cash_session = repo.open_session(
                cash_register_id=cash_register_id,
                opened_by_user_id=opened_by_user_id,
                opening_amount=opening_amount,
            )
            dto = _session_dto(cash_session, register.name)

        self._event_bus.publish(
            CashSessionOpenedEvent(cash_session_id=dto.id, cash_register_id=cash_register_id)
        )
        return dto

    def register_manual_movement(
        self,
        *,
        cash_session_id: int,
        movement_type: CashMovementType,
        amount: Decimal,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> None:
        if movement_type not in (CashMovementType.MANUAL_IN, CashMovementType.MANUAL_OUT):
            raise BusinessRuleViolationError(
                "Solo se pueden registrar movimientos manuales de ingreso o egreso."
            )
        if amount <= 0:
            raise BusinessRuleViolationError("El monto debe ser mayor que cero.")

        with session_scope() as session:
            repo = CashRegisterRepository(session)
            cash_session = repo.get_session(cash_session_id)
            if cash_session is None:
                raise NotFoundError(f"No existe la sesión de caja con id={cash_session_id}.")
            if cash_session.status is not CashSessionStatus.OPEN:
                raise BusinessRuleViolationError("La sesión de caja ya está cerrada.")

            repo.add_movement(
                cash_session_id=cash_session_id,
                movement_type=movement_type,
                amount=amount,
                reason=reason,
                created_by_user_id=created_by_user_id,
            )

    def register_sale_movement(self, *, cash_session_id: int, amount: Decimal) -> None:
        """Registra el componente en efectivo de una venta completada.

        Llamada directamente por `SalesService` (no vía evento) porque debe
        formar parte de la misma operación atómica que completar la venta
        — ver ARCHITECTURE.md §5b. Solo se llama con `amount > 0` (la parte
        de la venta pagada en efectivo); pagos con tarjeta/transferencia no
        afectan el efectivo físico de la caja.
        """
        if amount <= 0:
            raise BusinessRuleViolationError(
                "El monto de la venta en efectivo debe ser mayor que cero."
            )

        with session_scope() as session:
            repo = CashRegisterRepository(session)
            cash_session = repo.get_session(cash_session_id)
            if cash_session is None:
                raise NotFoundError(f"No existe la sesión de caja con id={cash_session_id}.")
            if cash_session.status is not CashSessionStatus.OPEN:
                raise BusinessRuleViolationError("La sesión de caja ya está cerrada.")

            repo.add_movement(
                cash_session_id=cash_session_id,
                movement_type=CashMovementType.SALE,
                amount=amount,
                reason=None,
                created_by_user_id=None,
            )

    def register_refund_movement(
        self, *, cash_session_id: int, amount: Decimal, reason: str | None
    ) -> None:
        """Registra la salida de efectivo por la devolución de una venta anulada."""
        if amount <= 0:
            raise BusinessRuleViolationError("El monto a devolver debe ser mayor que cero.")

        with session_scope() as session:
            repo = CashRegisterRepository(session)
            cash_session = repo.get_session(cash_session_id)
            if cash_session is None:
                raise NotFoundError(f"No existe la sesión de caja con id={cash_session_id}.")
            if cash_session.status is not CashSessionStatus.OPEN:
                raise BusinessRuleViolationError(
                    "No se puede devolver efectivo: la sesión de caja ya está cerrada."
                )

            repo.add_movement(
                cash_session_id=cash_session_id,
                movement_type=CashMovementType.REFUND,
                amount=amount,
                reason=reason,
                created_by_user_id=None,
            )

    def list_movements(self, cash_session_id: int) -> list[CashMovementDTO]:
        with session_scope() as session:
            repo = CashRegisterRepository(session)
            return [
                CashMovementDTO(
                    id=m.id,
                    movement_type=m.movement_type,
                    amount=m.amount,
                    reason=m.reason,
                    created_at=m.created_at,
                )
                for m in repo.list_movements(cash_session_id)
            ]

    def calculate_expected_amount(self, cash_session_id: int) -> Decimal:
        with session_scope() as session:
            repo = CashRegisterRepository(session)
            cash_session = repo.get_session(cash_session_id)
            if cash_session is None:
                raise NotFoundError(f"No existe la sesión de caja con id={cash_session_id}.")
            return self._expected_amount(repo, cash_session)

    def _expected_amount(self, repo: CashRegisterRepository, cash_session: CashSession) -> Decimal:
        expected = cash_session.opening_amount
        for movement_type in _INFLOW_TYPES:
            expected += repo.sum_movements(cash_session.id, movement_type)
        for movement_type in _OUTFLOW_TYPES:
            expected -= repo.sum_movements(cash_session.id, movement_type)
        return expected

    def close_session(
        self, *, cash_session_id: int, closed_by_user_id: int, counted_amount: Decimal
    ) -> CashSessionDTO:
        if counted_amount < 0:
            raise BusinessRuleViolationError("El monto contado no puede ser negativo.")

        with session_scope() as session:
            repo = CashRegisterRepository(session)
            cash_session = repo.get_session(cash_session_id)
            if cash_session is None:
                raise NotFoundError(f"No existe la sesión de caja con id={cash_session_id}.")
            if cash_session.status is not CashSessionStatus.OPEN:
                raise BusinessRuleViolationError("La sesión de caja ya está cerrada.")

            expected_amount = self._expected_amount(repo, cash_session)
            difference = counted_amount - expected_amount

            repo.close_session(
                cash_session,
                closed_by_user_id=closed_by_user_id,
                closing_amount=counted_amount,
                expected_amount=expected_amount,
                difference=difference,
                closed_at=datetime.now(UTC),
            )
            register = repo.get_register(cash_session.cash_register_id)
            assert register is not None
            dto = _session_dto(cash_session, register.name)

        self._event_bus.publish(
            CashSessionClosedEvent(cash_session_id=dto.id, difference=difference)
        )
        return dto
