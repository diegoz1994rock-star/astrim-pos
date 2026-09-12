"""Pruebas de UI de `KitchenView` (backend `offscreen`): filtros y buscador
sobre la lista de tarjetas ya cargada — no se ejercita el doble clic (abre
un `QDialog` modal bloqueante, mismo motivo ya documentado en
`tests/ui/sales/test_sale_view.py` para otros diálogos)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from pos.modules.kitchen.presentation.kitchen_view import KitchenView
from pos.modules.restaurant.application.dto import DispatchOrderCardDTO
from pos.modules.restaurant.domain.enums import OrderOrigin, OrderStatus


def _card(
    order_id: int,
    *,
    origin: OrderOrigin = OrderOrigin.VENDEDOR,
    is_paid: bool = False,
    dispatch_status: OrderStatus = OrderStatus.PENDING,
    customer_name: str = "Cliente",
) -> DispatchOrderCardDTO:
    return DispatchOrderCardDTO(
        order_id=order_id,
        origin=origin,
        customer_name=customer_name,
        customer_document="10203040",
        is_paid=is_paid,
        caja_name="Caja 1" if is_paid else None,
        dispatch_status=dispatch_status,
        item_count=1,
        total_units=1,
        items=[],
        created_at=datetime.now(UTC),
    )


def _make_view(qtbot: QtBot) -> KitchenView:
    view = KitchenView(Mock())
    qtbot.addWidget(view)
    return view


def test_default_filter_shows_every_active_order(qtbot: QtBot) -> None:
    """El filtro por defecto es "Todos", no "Pendientes" — si fuera
    "Pendientes", una tarjeta desaparecería de la vista por defecto apenas
    avanzara de estado con "Siguiente proceso", que es exactamente el
    comportamiento que no se quiere (ver `_DEFAULT_FILTER`)."""
    view = _make_view(qtbot)

    view._on_queue_loaded(
        [
            _card(1, dispatch_status=OrderStatus.PENDING),
            _card(2, dispatch_status=OrderStatus.PREPARING),
            _card(3, dispatch_status=OrderStatus.DELIVERED),
        ]
    )

    assert view._cards_layout.count() == 3


def test_card_stays_visible_across_status_changes_under_default_filter(qtbot: QtBot) -> None:
    """El caso concreto reportado: seleccionar un pedido, avanzarlo con
    "Siguiente proceso" (lo que en la práctica dispara un nuevo
    `queue_loaded` con el mismo pedido en su nuevo estado) no debe hacerlo
    desaparecer de la tarjeta — debe seguir en la misma lista hasta que se
    archive de verdad (tercer clic, ya excluido por el backend)."""
    view = _make_view(qtbot)
    view._on_queue_loaded([_card(1, dispatch_status=OrderStatus.PENDING)])
    assert view._cards_layout.count() == 1

    view._on_queue_loaded([_card(1, dispatch_status=OrderStatus.PREPARING)])
    assert view._cards_layout.count() == 1

    view._on_queue_loaded([_card(1, dispatch_status=OrderStatus.DELIVERED)])
    assert view._cards_layout.count() == 1

    # Solo al archivarse (el backend ya no lo devuelve en la cola) desaparece.
    view._on_queue_loaded([])
    assert view._cards_layout.count() == 0


def test_todos_filter_shows_all_orders(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded(
        [
            _card(1, dispatch_status=OrderStatus.PENDING),
            _card(2, dispatch_status=OrderStatus.DELIVERED),
        ]
    )

    view._on_filter_clicked("Todos")

    assert view._cards_layout.count() == 2


def test_pagados_filter_shows_only_paid_orders(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded([_card(1, is_paid=True), _card(2, is_paid=False)])

    view._on_filter_clicked("Pagados")

    assert view._cards_layout.count() == 1


def test_origin_filters_split_vendedor_and_ventas(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded(
        [
            _card(1, origin=OrderOrigin.VENDEDOR),
            _card(2, origin=OrderOrigin.VENTAS),
        ]
    )
    view._on_filter_clicked("Todos")

    view._on_filter_clicked("Pedidos del Vendedor")
    assert view._cards_layout.count() == 1

    view._on_filter_clicked("Pedidos de Ventas")
    assert view._cards_layout.count() == 1


def test_search_filters_by_customer_name(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded(
        [
            _card(1, customer_name="Mario Gómez"),
            _card(2, customer_name="Sofía Martínez"),
        ]
    )
    view._on_filter_clicked("Todos")

    view._search_edit.setText("Sofía")

    assert view._cards_layout.count() == 1


def test_pending_count_label_counts_only_pending_orders(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_queue_loaded(
        [
            _card(1, dispatch_status=OrderStatus.PENDING),
            _card(2, dispatch_status=OrderStatus.PREPARING),
            _card(3, dispatch_status=OrderStatus.DELIVERED),
        ]
    )

    assert view._pending_count_label.text() == "Pedidos pendientes (1)"


def test_en_preparacion_filter_shows_only_preparing_orders(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded(
        [
            _card(1, dispatch_status=OrderStatus.PENDING),
            _card(2, dispatch_status=OrderStatus.PREPARING),
            _card(3, dispatch_status=OrderStatus.DELIVERED),
        ]
    )

    view._on_filter_clicked("En preparación")

    assert view._cards_layout.count() == 1


def test_clicking_a_card_selects_it(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded([_card(1), _card(2)])

    view._on_card_clicked(2)

    assert view._selected_order_id == 2


def test_next_process_without_selection_shows_info_and_does_not_call_view_model(
    qtbot: QtBot,
) -> None:
    view = _make_view(qtbot)
    view._show_info = Mock()

    view._on_next_process_clicked()

    view._show_info.assert_called_once_with("Seleccione un pedido para continuar.")
    view._view_model.advance_dispatch_status.assert_not_called()


def test_next_process_with_selection_advances_that_order(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded([_card(1)])
    view._on_card_clicked(1)

    view._on_next_process_clicked()

    view._view_model.advance_dispatch_status.assert_called_once_with(1)


def test_selection_clears_when_selected_order_leaves_the_queue(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_queue_loaded([_card(1), _card(2)])
    view._on_card_clicked(1)

    view._on_queue_loaded([_card(2)])

    assert view._selected_order_id is None


def test_card_shows_large_centered_status_text_and_keeps_the_rest_of_the_data(
    qtbot: QtBot,
) -> None:
    view = _make_view(qtbot)

    view._on_queue_loaded([_card(1, dispatch_status=OrderStatus.PREPARING, is_paid=True)])

    card_widget = view._cards_layout.itemAt(0).widget()
    labels = {label.text() for label in card_widget.findChildren(QLabel)}
    assert "EN PREPARACIÓN" in labels
    status_label = next(
        label for label in card_widget.findChildren(QLabel) if label.text() == "EN PREPARACIÓN"
    )
    assert status_label.property("sizeVariant") == "status"
    assert status_label.property("role") == "info"
    # El resto de la información de la tarjeta se conserva.
    assert "PAGADO" in labels
    assert "1 productos" in labels
    assert "1 unidades" in labels
    assert "Vendedor" in labels
