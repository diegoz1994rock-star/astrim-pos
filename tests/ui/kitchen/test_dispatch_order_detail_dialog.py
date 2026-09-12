"""Pruebas de UI de `DispatchOrderDetailDialog` (backend `offscreen`): se
construye sin lanzar `exec()` (modal bloqueante) — solo se verifica que se
arma sin errores y que "Marcar como entregado" hace lo que promete."""

from __future__ import annotations

from datetime import UTC, datetime

from pytestqt.qtbot import QtBot

from pos.modules.kitchen.presentation.dispatch_order_detail_dialog import (
    DispatchOrderDetailDialog,
)
from pos.modules.restaurant.application.dto import DispatchOrderCardDTO, OrderItemDTO
from pos.modules.restaurant.domain.enums import OrderItemStatus, OrderOrigin, OrderStatus


def _card() -> DispatchOrderCardDTO:
    return DispatchOrderCardDTO(
        order_id=345,
        origin=OrderOrigin.VENDEDOR,
        customer_name="Mario Gómez",
        customer_document="10203040",
        is_paid=False,
        caja_name=None,
        dispatch_status=OrderStatus.PENDING,
        item_count=2,
        total_units=17,
        items=[
            OrderItemDTO(
                id=1,
                order_id=345,
                product_id=1,
                product_name="Cemento",
                quantity=2,
                notes=None,
                status=OrderItemStatus.PENDING,
            ),
            OrderItemDTO(
                id=2,
                order_id=345,
                product_id=2,
                product_name="Varillas",
                quantity=10,
                notes="Cortar a la mitad",
                status=OrderItemStatus.PENDING,
            ),
        ],
        created_at=datetime.now(UTC),
    )


def test_dialog_builds_without_errors(qtbot: QtBot) -> None:
    dialog = DispatchOrderDetailDialog(_card())
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Pedido #000345"
    assert dialog.was_marked_delivered() is False


def test_deliver_button_disabled_when_already_delivered(qtbot: QtBot) -> None:
    card = _card()
    delivered_card = DispatchOrderCardDTO(
        **{**card.__dict__, "dispatch_status": OrderStatus.DELIVERED}
    )
    dialog = DispatchOrderDetailDialog(delivered_card)
    qtbot.addWidget(dialog)

    assert dialog._deliver_button.isEnabled() is False


def test_clicking_deliver_marks_dialog_and_accepts(qtbot: QtBot) -> None:
    dialog = DispatchOrderDetailDialog(_card())
    qtbot.addWidget(dialog)

    dialog._on_deliver_clicked()

    assert dialog.was_marked_delivered() is True
