"""Pruebas de integración de RestaurantService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import (
    OrderStatus,
    OrderType,
    TableSessionStatus,
    TableStatus,
)
from tests.integration.restaurant.conftest import RestaurantFixture


def test_create_table_rejects_empty_name(sqlite_engine: None) -> None:
    service = RestaurantService()
    with pytest.raises(BusinessRuleViolationError):
        service.create_table(name="  ")


def test_open_table_session_occupies_the_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService()
    table = service.create_table(name="Mesa 1")

    table_session = service.open_table_session(
        table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id
    )

    assert table_session.status is TableSessionStatus.OPEN
    tables = service.list_tables()
    assert tables[0].status is TableStatus.OCCUPIED


def test_cannot_open_an_already_occupied_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService()
    table = service.create_table(name="Mesa 1")
    service.open_table_session(table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id)

    with pytest.raises(BusinessRuleViolationError):
        service.open_table_session(table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id)


def test_close_table_session_frees_the_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService()
    table = service.create_table(name="Mesa 1")
    table_session = service.open_table_session(
        table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id
    )

    service.close_table_session(table_session.id)

    tables = service.list_tables()
    assert tables[0].status is TableStatus.FREE


def test_dine_in_order_requires_a_table_session(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService()
    with pytest.raises(BusinessRuleViolationError):
        service.create_order(
            table_session_id=None,
            order_type=OrderType.DINE_IN,
            items=[(restaurant_env.product_id, 1, None)],
        )


def test_takeaway_order_does_not_require_a_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService()
    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.TAKEAWAY,
        items=[(restaurant_env.product_id, 2, "sin cebolla")],
    )

    assert order.status is OrderStatus.PENDING
    assert len(order.items) == 1
    assert order.items[0].quantity == 2
    assert order.items[0].notes == "sin cebolla"
    assert order.items[0].product_name == "Plato del día"


def test_create_order_with_unknown_product_raises_not_found(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService()
    with pytest.raises(NotFoundError):
        service.create_order(
            table_session_id=None, order_type=OrderType.QUICK, items=[(99999, 1, None)]
        )


def test_list_orders_for_session_only_returns_that_sessions_orders(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService()
    table_a = service.create_table(name="Mesa A")
    table_b = service.create_table(name="Mesa B")
    session_a = service.open_table_session(
        table_id=table_a.id, waiter_user_id=restaurant_env.waiter_user_id
    )
    session_b = service.open_table_session(
        table_id=table_b.id, waiter_user_id=restaurant_env.waiter_user_id
    )
    service.create_order(
        table_session_id=session_a.id,
        order_type=OrderType.DINE_IN,
        items=[(restaurant_env.product_id, 1, None)],
    )
    service.create_order(
        table_session_id=session_b.id,
        order_type=OrderType.DINE_IN,
        items=[(restaurant_env.product_id, 3, None)],
    )

    orders_a = service.list_orders_for_session(session_a.id)

    assert len(orders_a) == 1
    assert orders_a[0].items[0].quantity == 1
