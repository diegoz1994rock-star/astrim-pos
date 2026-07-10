"""Pruebas de integración de CashRegisterService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.cash_register.domain.enums import CashMovementType, CashSessionStatus
from pos.modules.cash_register.domain.events import CashSessionClosedEvent, CashSessionOpenedEvent


def test_open_session_succeeds(register_id: int, user_id: int) -> None:
    service = CashRegisterService(EventBus())

    session = service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal("50000")
    )

    assert session.status is CashSessionStatus.OPEN
    assert session.opening_amount == Decimal("50000")


def test_open_session_publishes_event(register_id: int, user_id: int) -> None:
    bus = EventBus()
    received: list[CashSessionOpenedEvent] = []
    bus.subscribe(CashSessionOpenedEvent, received.append)
    service = CashRegisterService(bus)

    service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal(0)
    )

    assert len(received) == 1


def test_cannot_open_two_sessions_on_same_register(register_id: int, user_id: int) -> None:
    service = CashRegisterService(EventBus())
    service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal(0)
    )

    with pytest.raises(BusinessRuleViolationError):
        service.open_session(
            cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal(0)
        )


def test_manual_movements_affect_expected_amount(register_id: int, user_id: int) -> None:
    service = CashRegisterService(EventBus())
    session = service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal("100")
    )

    service.register_manual_movement(
        cash_session_id=session.id,
        movement_type=CashMovementType.MANUAL_IN,
        amount=Decimal("50"),
        reason="Ingreso extra",
        created_by_user_id=user_id,
    )
    service.register_manual_movement(
        cash_session_id=session.id,
        movement_type=CashMovementType.MANUAL_OUT,
        amount=Decimal("20"),
        reason="Compra de insumos",
        created_by_user_id=user_id,
    )

    expected = service.calculate_expected_amount(session.id)
    assert expected == Decimal("130")


def test_close_session_with_matching_count_has_zero_difference(
    register_id: int, user_id: int
) -> None:
    service = CashRegisterService(EventBus())
    session = service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal("100")
    )

    closed = service.close_session(
        cash_session_id=session.id, closed_by_user_id=user_id, counted_amount=Decimal("100")
    )

    assert closed.status is CashSessionStatus.CLOSED
    assert closed.difference == Decimal("0")


def test_close_session_with_shortfall_reports_negative_difference(
    register_id: int, user_id: int
) -> None:
    service = CashRegisterService(EventBus())
    session = service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal("100")
    )

    closed = service.close_session(
        cash_session_id=session.id, closed_by_user_id=user_id, counted_amount=Decimal("90")
    )

    assert closed.difference == Decimal("-10")


def test_close_session_publishes_event_with_difference(register_id: int, user_id: int) -> None:
    bus = EventBus()
    received: list[CashSessionClosedEvent] = []
    bus.subscribe(CashSessionClosedEvent, received.append)
    service = CashRegisterService(bus)
    session = service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal("100")
    )

    service.close_session(
        cash_session_id=session.id, closed_by_user_id=user_id, counted_amount=Decimal("95")
    )

    assert len(received) == 1
    assert received[0].difference == Decimal("-5")


def test_cannot_close_already_closed_session(register_id: int, user_id: int) -> None:
    service = CashRegisterService(EventBus())
    session = service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal("0")
    )
    service.close_session(
        cash_session_id=session.id, closed_by_user_id=user_id, counted_amount=Decimal("0")
    )

    with pytest.raises(BusinessRuleViolationError):
        service.close_session(
            cash_session_id=session.id, closed_by_user_id=user_id, counted_amount=Decimal("0")
        )


def test_cannot_register_movement_on_closed_session(register_id: int, user_id: int) -> None:
    service = CashRegisterService(EventBus())
    session = service.open_session(
        cash_register_id=register_id, opened_by_user_id=user_id, opening_amount=Decimal("0")
    )
    service.close_session(
        cash_session_id=session.id, closed_by_user_id=user_id, counted_amount=Decimal("0")
    )

    with pytest.raises(BusinessRuleViolationError):
        service.register_manual_movement(
            cash_session_id=session.id,
            movement_type=CashMovementType.MANUAL_IN,
            amount=Decimal("10"),
            reason=None,
            created_by_user_id=user_id,
        )
