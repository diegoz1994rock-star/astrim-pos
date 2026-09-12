"""Pruebas de `KitchenViewModel` con `KitchenService` simulado (`Mock`)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.kitchen.presentation.kitchen_view_model import KitchenViewModel
from pos.modules.restaurant.application.dto import DispatchOrderCardDTO
from pos.modules.restaurant.domain.enums import OrderOrigin, OrderStatus


def _card(order_id: int = 1) -> DispatchOrderCardDTO:
    return DispatchOrderCardDTO(
        order_id=order_id,
        origin=OrderOrigin.VENDEDOR,
        customer_name="Mario Gómez",
        customer_document="10203040",
        is_paid=False,
        caja_name=None,
        dispatch_status=OrderStatus.PENDING,
        item_count=1,
        total_units=2,
        items=[],
        created_at=datetime.now(UTC),
    )


def _make_view_model() -> tuple[KitchenViewModel, Mock]:
    kitchen_service = Mock()
    kitchen_service.list_dispatch_queue.return_value = [_card()]
    session_manager = Mock()
    session_manager.current.user_id = 7
    view_model = KitchenViewModel(kitchen_service, session_manager, EventBus())
    return view_model, kitchen_service


def test_load_calls_list_dispatch_queue(qtbot: QtBot) -> None:
    view_model, kitchen_service = _make_view_model()
    expected_queue = kitchen_service.list_dispatch_queue.return_value
    received: list[list[DispatchOrderCardDTO]] = []
    view_model.queue_loaded.connect(received.append)

    view_model.load()

    kitchen_service.list_dispatch_queue.assert_called_once()
    assert received == [expected_queue]


def test_mark_delivered_reloads_queue_on_success(qtbot: QtBot) -> None:
    view_model, kitchen_service = _make_view_model()
    reloads = []
    view_model.queue_loaded.connect(reloads.append)

    view_model.mark_delivered(1)

    kitchen_service.mark_order_delivered.assert_called_once_with(1, delivered_by_user_id=7)
    assert len(reloads) == 1


def test_mark_delivered_emits_error_on_domain_error(qtbot: QtBot) -> None:
    view_model, kitchen_service = _make_view_model()
    kitchen_service.mark_order_delivered.side_effect = BusinessRuleViolationError("ya entregado")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.mark_delivered(1)

    assert errors == ["ya entregado"]


def test_advance_dispatch_status_reloads_queue_on_success(qtbot: QtBot) -> None:
    view_model, kitchen_service = _make_view_model()
    reloads = []
    view_model.queue_loaded.connect(reloads.append)

    view_model.advance_dispatch_status(1)

    kitchen_service.advance_dispatch_status.assert_called_once_with(1, changed_by_user_id=7)
    assert len(reloads) == 1


def test_advance_dispatch_status_emits_error_on_domain_error(qtbot: QtBot) -> None:
    view_model, kitchen_service = _make_view_model()
    kitchen_service.advance_dispatch_status.side_effect = BusinessRuleViolationError("no existe")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.advance_dispatch_status(1)

    assert errors == ["no existe"]
