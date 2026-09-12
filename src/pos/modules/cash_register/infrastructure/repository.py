"""Acceso a datos de caja: puntos de caja, sesiones y movimientos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.cash_register.domain.enums import CashMovementType, CashSessionStatus
from pos.modules.cash_register.infrastructure.models import (
    CashMovement,
    CashRegister,
    CashSession,
)


class CashRegisterRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_registers(self) -> list[CashRegister]:
        return list(
            self._session.scalars(
                select(CashRegister).where(CashRegister.is_active.is_(True)).order_by(CashRegister.name)
            )
        )

    def list_all_registers(self) -> list[CashRegister]:
        return list(self._session.scalars(select(CashRegister).order_by(CashRegister.name)))

    def get_register(self, register_id: int) -> CashRegister | None:
        return self._session.get(CashRegister, register_id)

    def get_register_by_name(self, name: str) -> CashRegister | None:
        return self._session.scalar(select(CashRegister).where(CashRegister.name == name))

    def create_register(self, *, name: str, location: str | None) -> CashRegister:
        register = CashRegister(name=name, location=location, is_active=True)
        self._session.add(register)
        self._session.flush()
        return register

    def update_register(self, register: CashRegister, *, name: str, location: str | None) -> None:
        register.name = name
        register.location = location
        self._session.flush()

    def set_register_active(self, register: CashRegister, is_active: bool) -> None:
        register.is_active = is_active

    def has_sessions(self, register_id: int) -> bool:
        return (
            self._session.scalar(
                select(CashSession.id).where(CashSession.cash_register_id == register_id)
            )
            is not None
        )

    def delete_register(self, register: CashRegister) -> None:
        self._session.delete(register)
        self._session.flush()

    def get_open_session(self, register_id: int) -> CashSession | None:
        return self._session.scalar(
            select(CashSession).where(
                CashSession.cash_register_id == register_id,
                CashSession.status == CashSessionStatus.OPEN,
            )
        )

    def get_session(self, session_id: int) -> CashSession | None:
        return self._session.get(CashSession, session_id)

    def open_session(
        self, *, cash_register_id: int, opened_by_user_id: int, opening_amount: Decimal
    ) -> CashSession:
        cash_session = CashSession(
            cash_register_id=cash_register_id,
            opened_by_user_id=opened_by_user_id,
            opening_amount=opening_amount,
            status=CashSessionStatus.OPEN,
        )
        self._session.add(cash_session)
        self._session.flush()
        return cash_session

    def add_movement(
        self,
        *,
        cash_session_id: int,
        movement_type: CashMovementType,
        amount: Decimal,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> CashMovement:
        movement = CashMovement(
            cash_session_id=cash_session_id,
            movement_type=movement_type,
            amount=amount,
            reason=reason,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(movement)
        self._session.flush()
        return movement

    def sum_movements(self, cash_session_id: int, movement_type: CashMovementType) -> Decimal:
        total = self._session.scalar(
            select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
                CashMovement.cash_session_id == cash_session_id,
                CashMovement.movement_type == movement_type,
            )
        )
        return total if total is not None else Decimal(0)

    def list_movements(self, cash_session_id: int) -> list[CashMovement]:
        return list(
            self._session.scalars(
                select(CashMovement)
                .where(CashMovement.cash_session_id == cash_session_id)
                .order_by(CashMovement.created_at.desc())
            )
        )

    def close_session(
        self,
        cash_session: CashSession,
        *,
        closed_by_user_id: int,
        closing_amount: Decimal,
        expected_amount: Decimal,
        difference: Decimal,
        closed_at: datetime,
    ) -> None:
        cash_session.status = CashSessionStatus.CLOSED
        cash_session.closed_by_user_id = closed_by_user_id
        cash_session.closing_amount = closing_amount
        cash_session.expected_amount = expected_amount
        cash_session.difference = difference
        cash_session.closed_at = closed_at
