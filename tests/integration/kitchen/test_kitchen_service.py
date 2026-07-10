"""Pruebas de integración de KitchenService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import OrderItemStatus, OrderType
from tests.integration.kitchen.conftest import KitchenFixture


def test_new_order_items_start_in_the_queue_as_pending(kitchen_env: KitchenFixture) -> None:
    restaurant_service = RestaurantService()
    kitchen_service = KitchenService()
    restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.TAKEAWAY,
        items=[(kitchen_env.product_id, 1, None)],
    )

    queue = kitchen_service.list_queue()

    assert len(queue) == 1
    assert queue[0].status is OrderItemStatus.PENDING
    assert queue[0].product_name == "Plato del día"
    assert queue[0].table_name is None


def test_advance_item_moves_through_the_full_sequence(kitchen_env: KitchenFixture) -> None:
    restaurant_service = RestaurantService()
    kitchen_service = KitchenService()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    item_id = order.items[0].id

    preparing = kitchen_service.advance_item(item_id, changed_by_user_id=None)
    assert preparing.status is OrderItemStatus.PREPARING

    ready = kitchen_service.advance_item(item_id, changed_by_user_id=None)
    assert ready.status is OrderItemStatus.READY

    delivered = kitchen_service.advance_item(item_id, changed_by_user_id=None)
    assert delivered.status is OrderItemStatus.DELIVERED


def test_advance_item_past_delivered_is_rejected(kitchen_env: KitchenFixture) -> None:
    restaurant_service = RestaurantService()
    kitchen_service = KitchenService()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    item_id = order.items[0].id
    for _ in range(3):
        kitchen_service.advance_item(item_id, changed_by_user_id=None)

    with pytest.raises(BusinessRuleViolationError):
        kitchen_service.advance_item(item_id, changed_by_user_id=None)


def test_delivered_items_leave_the_queue(kitchen_env: KitchenFixture) -> None:
    restaurant_service = RestaurantService()
    kitchen_service = KitchenService()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    item_id = order.items[0].id
    for _ in range(3):
        kitchen_service.advance_item(item_id, changed_by_user_id=None)

    assert kitchen_service.list_queue() == []


def test_queue_shows_table_name_for_dine_in_orders(kitchen_env: KitchenFixture) -> None:
    restaurant_service = RestaurantService()
    kitchen_service = KitchenService()
    table = restaurant_service.create_table(name="Mesa 7")
    table_session = restaurant_service.open_table_session(
        table_id=table.id, waiter_user_id=kitchen_env.waiter_user_id
    )
    restaurant_service.create_order(
        table_session_id=table_session.id,
        order_type=OrderType.DINE_IN,
        items=[(kitchen_env.product_id, 1, None)],
    )

    queue = kitchen_service.list_queue()

    assert queue[0].table_name == "Mesa 7"
