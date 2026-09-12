"""Pruebas de integración de RestaurantService contra SQLite real."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import (
    OrderItemStatus,
    OrderOrigin,
    OrderStatus,
    OrderType,
    TableSessionStatus,
    TableStatus,
)
from pos.modules.restaurant.domain.events import OrderCreatedEvent
from pos.modules.restaurant.infrastructure.repository import RestaurantRepository
from pos.modules.sales.application.dto import SaleDTO, SaleItemDTO
from pos.modules.sales.domain.enums import SaleStatus, SaleType
from pos.modules.sales.infrastructure.models import Sale
from tests.integration.restaurant.conftest import RestaurantFixture


def test_create_table_rejects_empty_name(sqlite_engine: None) -> None:
    service = RestaurantService(EventBus())
    with pytest.raises(BusinessRuleViolationError):
        service.create_table(name="  ")


def test_open_table_session_occupies_the_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService(EventBus())
    table = service.create_table(name="Mesa 1")

    table_session = service.open_table_session(
        table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id
    )

    assert table_session.status is TableSessionStatus.OPEN
    tables = service.list_tables()
    assert tables[0].status is TableStatus.OCCUPIED


def test_cannot_open_an_already_occupied_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService(EventBus())
    table = service.create_table(name="Mesa 1")
    service.open_table_session(table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id)

    with pytest.raises(BusinessRuleViolationError):
        service.open_table_session(table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id)


def test_close_table_session_frees_the_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService(EventBus())
    table = service.create_table(name="Mesa 1")
    table_session = service.open_table_session(
        table_id=table.id, waiter_user_id=restaurant_env.waiter_user_id
    )

    service.close_table_session(table_session.id)

    tables = service.list_tables()
    assert tables[0].status is TableStatus.FREE


def test_dine_in_order_requires_a_table_session(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService(EventBus())
    with pytest.raises(BusinessRuleViolationError):
        service.create_order(
            table_session_id=None,
            order_type=OrderType.DINE_IN,
            items=[(restaurant_env.product_id, 1, None)],
        )


def test_takeaway_order_does_not_require_a_table(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService(EventBus())
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
    service = RestaurantService(EventBus())
    with pytest.raises(NotFoundError):
        service.create_order(
            table_session_id=None, order_type=OrderType.QUICK, items=[(99999, 1, None)]
        )


def test_list_orders_for_session_only_returns_that_sessions_orders(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService(EventBus())
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


def test_create_order_publishes_order_created_event(restaurant_env: RestaurantFixture) -> None:
    bus = EventBus()
    received: list[OrderCreatedEvent] = []
    bus.subscribe(OrderCreatedEvent, received.append)
    service = RestaurantService(bus)

    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 1, None)],
        created_by_user_id=restaurant_env.waiter_user_id,
    )

    assert len(received) == 1
    assert received[0].order_id == order.id
    assert received[0].created_by_user_id == restaurant_env.waiter_user_id


def test_new_order_has_no_sale_and_appears_as_pending_payment(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService(EventBus())

    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 2, None)],
    )

    assert order.sale_id is None
    pending = service.list_pending_payment_orders()
    assert any(o.id == order.id for o in pending)


def test_link_order_to_sale_removes_it_from_pending_payment(
    restaurant_env: RestaurantFixture,
) -> None:
    from pos.core.database.session import session_scope
    from pos.modules.sales.infrastructure.models import Sale

    service = RestaurantService(EventBus())
    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 1, None)],
    )
    with session_scope() as session:
        sale = Sale()
        session.add(sale)
        session.flush()
        sale_id = sale.id

    service.link_order_to_sale(order.id, sale_id=sale_id)

    pending = service.list_pending_payment_orders()
    assert all(o.id != order.id for o in pending)


def test_link_order_to_sale_for_unknown_order_raises_not_found(sqlite_engine: None) -> None:
    service = RestaurantService(EventBus())

    with pytest.raises(NotFoundError):
        service.link_order_to_sale(99999, sale_id=1)


def test_create_order_with_blank_customer_name_defaults_to_consumidor_final(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService(EventBus())

    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 1, None)],
        customer_name="   ",
    )

    assert order.customer_name == "Consumidor Final"


def test_create_order_keeps_the_given_customer_name(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService(EventBus())

    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 1, None)],
        customer_name="Carlos Pérez",
    )

    assert order.customer_name == "Carlos Pérez"


def test_pending_payment_orders_have_no_ready_at_before_any_item_is_ready(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService(EventBus())
    service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 1, None)],
    )

    pending = service.list_pending_payment_orders()

    assert pending[0].ready_at is None


def test_pending_payment_orders_report_ready_at_once_an_item_reaches_ready(
    restaurant_env: RestaurantFixture,
) -> None:
    from pos.modules.cash_register.application.cash_register_service import CashRegisterService
    from pos.modules.customers.application.customer_service import CustomerManagementService
    from pos.modules.inventory.application.inventory_service import InventoryService
    from pos.modules.kitchen.application.kitchen_service import KitchenService
    from pos.modules.sales.application.sale_service import SalesService
    from pos.modules.users.application.user_management_service import UserManagementService

    service = RestaurantService(EventBus())
    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 1, None)],
    )
    kitchen_bus = EventBus()
    kitchen_service = KitchenService(
        UserManagementService(kitchen_bus),
        RestaurantService(kitchen_bus),
        SalesService(
            kitchen_bus,
            InventoryService(kitchen_bus),
            CashRegisterService(kitchen_bus),
            CustomerManagementService(),
        ),
        CashRegisterService(kitchen_bus),
    )
    item_id = order.items[0].id
    kitchen_service.advance_item(item_id, changed_by_user_id=None)  # PREPARING
    kitchen_service.advance_item(item_id, changed_by_user_id=None)  # READY

    pending = service.list_pending_payment_orders()

    assert pending[0].ready_at is not None


def _sale_dto_for_dispatch(
    restaurant_env: RestaurantFixture,
    *,
    quantity: Decimal = Decimal("2"),
    customer_name: str | None = "Sofía Martínez",
    customer_document: str | None = "50987654",
) -> SaleDTO:
    """`Order.sale_id` tiene FK real a `sales.id` — hace falta una fila
    `Sale` persistida de verdad, no un id inventado."""
    with session_scope() as session:
        sale = Sale(sale_type=SaleType.COUNTER, status=SaleStatus.COMPLETED)
        session.add(sale)
        session.flush()
        sale_id = sale.id
    return SaleDTO(
        id=sale_id,
        status=SaleStatus.COMPLETED,
        sale_type=SaleType.COUNTER,
        customer_id=None,
        subtotal=Decimal("30000"),
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("30000"),
        created_at=datetime.now(UTC),
        customer_name=customer_name,
        customer_document=customer_document,
        items=[
            SaleItemDTO(
                id=1,
                product_id=restaurant_env.product_id,
                product_name="Plato del día",
                quantity=quantity,
                unit_price=Decimal("15000"),
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                line_total=Decimal("30000"),
            )
        ],
    )


def test_create_order_from_sale_creates_a_prepaid_order(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService(EventBus())
    sale = _sale_dto_for_dispatch(restaurant_env)

    order = service.create_order_from_sale(sale, created_by_user_id=restaurant_env.waiter_user_id)

    assert order.sale_id == sale.id
    assert order.origin is OrderOrigin.VENTAS
    assert order.customer_name == "Sofía Martínez"
    assert order.customer_document == "50987654"
    assert order.items[0].quantity == 2
    assert order.id not in [o.id for o in service.list_pending_payment_orders()]


def test_create_order_from_sale_publishes_order_created_event(
    restaurant_env: RestaurantFixture,
) -> None:
    bus = EventBus()
    received: list[OrderCreatedEvent] = []
    bus.subscribe(OrderCreatedEvent, received.append)
    service = RestaurantService(bus)
    sale = _sale_dto_for_dispatch(restaurant_env)

    order = service.create_order_from_sale(sale)

    assert len(received) == 1
    assert received[0].order_id == order.id


def test_create_order_from_sale_rounds_fractional_quantities_up(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService(EventBus())
    sale = _sale_dto_for_dispatch(restaurant_env, quantity=Decimal("0.350"))

    order = service.create_order_from_sale(sale)

    assert order.items[0].quantity == 1


def test_create_order_from_sale_defaults_customer_name_when_blank(
    restaurant_env: RestaurantFixture,
) -> None:
    service = RestaurantService(EventBus())
    sale = _sale_dto_for_dispatch(restaurant_env, customer_name=None, customer_document=None)

    order = service.create_order_from_sale(sale)

    assert order.customer_name == "Consumidor Final"
    assert order.customer_document is None


def test_mark_order_delivered_cascades_to_all_items(restaurant_env: RestaurantFixture) -> None:
    service = RestaurantService(EventBus())
    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 2, None)],
    )

    delivered = service.mark_order_delivered(
        order.id, delivered_by_user_id=restaurant_env.waiter_user_id
    )

    assert delivered.status is OrderStatus.DELIVERED
    assert all(item.status is OrderItemStatus.DELIVERED for item in delivered.items)
    assert delivered.dispatched_by_user_id == restaurant_env.waiter_user_id


def test_advance_dispatch_status_follows_pending_preparing_delivered_archived(
    restaurant_env: RestaurantFixture,
) -> None:
    """Flujo completo del botón "Siguiente proceso" de Despacho: cada
    clic avanza un paso — Pendiente → En preparación → Entregado →
    Archivado (deja de listarse en Despacho, ver
    `RestaurantRepository.list_dispatch_queue`)."""
    service = RestaurantService(EventBus())
    order = service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(restaurant_env.product_id, 2, None)],
    )
    assert order.status is OrderStatus.PENDING

    after_first_click = service.advance_dispatch_status(
        order.id, changed_by_user_id=restaurant_env.waiter_user_id
    )
    assert after_first_click.status is OrderStatus.PREPARING

    after_second_click = service.advance_dispatch_status(
        order.id, changed_by_user_id=restaurant_env.waiter_user_id
    )
    assert after_second_click.status is OrderStatus.DELIVERED
    assert all(item.status is OrderItemStatus.DELIVERED for item in after_second_click.items)
    assert after_second_click.dispatched_by_user_id == restaurant_env.waiter_user_id

    after_third_click = service.advance_dispatch_status(
        order.id, changed_by_user_id=restaurant_env.waiter_user_id
    )
    assert after_third_click.status is OrderStatus.ARCHIVED

    with session_scope() as session:
        repo = RestaurantRepository(session)
        assert repo.get_order(order.id) is not None, "el pedido debe seguir existiendo"
        assert order.id not in [o.id for o in repo.list_dispatch_queue()]


def test_advance_dispatch_status_for_unknown_order_raises_not_found(
    sqlite_engine: None,
) -> None:
    service = RestaurantService(EventBus())

    with pytest.raises(NotFoundError):
        service.advance_dispatch_status(999)
