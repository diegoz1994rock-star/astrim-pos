"""Pruebas de integración de KitchenService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import OrderItemStatus, OrderStatus, OrderType
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.users.application.user_management_service import UserManagementService
from tests.integration.kitchen.conftest import KitchenFixture


def _make_kitchen_service() -> KitchenService:
    event_bus = EventBus()
    return KitchenService(
        UserManagementService(event_bus),
        RestaurantService(event_bus),
        SalesService(
            event_bus,
            InventoryService(event_bus),
            CashRegisterService(event_bus),
            CustomerManagementService(),
        ),
        CashRegisterService(event_bus),
    )


def test_new_order_items_start_in_the_queue_as_pending(kitchen_env: KitchenFixture) -> None:
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
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
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
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
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
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
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    item_id = order.items[0].id
    for _ in range(3):
        kitchen_service.advance_item(item_id, changed_by_user_id=None)

    assert kitchen_service.list_queue() == []


def test_paid_orders_leave_the_queue(kitchen_env: KitchenFixture) -> None:
    """Cobrar un pedido lo saca de Despacho automáticamente, sin importar
    en qué estado de preparación quedaron sus ítems — no hace falta
    marcarlos entregados a mano."""
    from pos.core.database.session import session_scope
    from pos.modules.sales.infrastructure.models import Sale

    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    assert len(kitchen_service.list_queue()) == 1

    with session_scope() as session:
        sale = Sale()
        session.add(sale)
        session.flush()
        sale_id = sale.id
    restaurant_service.link_order_to_sale(order.id, sale_id=sale_id)

    assert kitchen_service.list_queue() == []


def test_list_dispatch_queue_shows_unpaid_orders_with_no_caja(kitchen_env: KitchenFixture) -> None:
    from pos.modules.restaurant.domain.enums import OrderOrigin

    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 2, None)],
        customer_name="Mario Gómez",
        customer_document="10203040",
    )

    cards = kitchen_service.list_dispatch_queue()

    assert len(cards) == 1
    assert cards[0].is_paid is False
    assert cards[0].caja_name is None
    assert cards[0].sale_id is None
    assert cards[0].origin is OrderOrigin.VENDEDOR
    assert cards[0].customer_name == "Mario Gómez"
    assert cards[0].customer_document == "10203040"
    assert cards[0].item_count == 1
    assert cards[0].total_units == 2


def test_list_dispatch_queue_resolves_caja_name_once_paid(kitchen_env: KitchenFixture) -> None:
    from pos.core.database.session import session_scope
    from pos.modules.cash_register.infrastructure.models import CashRegister, CashSession
    from pos.modules.sales.infrastructure.models import Sale

    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    with session_scope() as session:
        register = CashRegister(name="Caja principal")
        session.add(register)
        session.flush()
        cash_session = CashSession(
            cash_register_id=register.id,
            opened_by_user_id=kitchen_env.waiter_user_id,
            opening_amount=Decimal("0"),
        )
        session.add(cash_session)
        sale = Sale(cash_session_id=None)
        session.add(sale)
        session.flush()
        sale.cash_session_id = cash_session.id
        sale_id = sale.id
    restaurant_service.link_order_to_sale(order.id, sale_id=sale_id)

    cards = kitchen_service.list_dispatch_queue()

    assert cards[0].is_paid is True
    assert cards[0].caja_name == "Caja principal"
    assert cards[0].sale_id == sale_id


def test_list_dispatch_queue_includes_delivered_orders(kitchen_env: KitchenFixture) -> None:
    """La exclusión de "entregados" es responsabilidad de la vista (filtro
    "Pendientes" por defecto), no de este servicio — que devuelve todo lo
    no cancelado para que los demás chips (Todos/Entregados) funcionen."""
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    restaurant_service.mark_order_delivered(order.id, delivered_by_user_id=None)

    cards = kitchen_service.list_dispatch_queue()

    assert len(cards) == 1
    assert cards[0].dispatch_status is OrderStatus.DELIVERED


def test_mark_order_delivered_via_kitchen_service_delegates_to_restaurant_service(
    kitchen_env: KitchenFixture,
) -> None:
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )

    kitchen_service.mark_order_delivered(order.id, delivered_by_user_id=kitchen_env.waiter_user_id)

    cards = kitchen_service.list_dispatch_queue()
    assert cards[0].dispatch_status is OrderStatus.DELIVERED
    assert cards[0].dispatched_by_user_name == "Mesero Uno"
    assert all(item.status is OrderItemStatus.DELIVERED for item in cards[0].items)


def test_advance_dispatch_status_via_kitchen_service_delegates_to_restaurant_service(
    kitchen_env: KitchenFixture,
) -> None:
    """Botón "Siguiente proceso" de Despacho — `KitchenService` delega en
    `RestaurantService.advance_dispatch_status`, sin lógica propia."""
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )

    kitchen_service.advance_dispatch_status(
        order.id, changed_by_user_id=kitchen_env.waiter_user_id
    )

    cards = kitchen_service.list_dispatch_queue()
    assert cards[0].dispatch_status is OrderStatus.PREPARING


def test_list_dispatch_queue_excludes_archived_orders(kitchen_env: KitchenFixture) -> None:
    """Un pedido archivado (tercer clic en "Siguiente proceso" sobre uno
    ya entregado) deja de listarse en Despacho, igual que uno cancelado."""
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
    order = restaurant_service.create_order(
        table_session_id=None,
        order_type=OrderType.QUICK,
        items=[(kitchen_env.product_id, 1, None)],
    )
    kitchen_service.advance_dispatch_status(order.id, changed_by_user_id=None)  # -> PREPARING
    kitchen_service.advance_dispatch_status(order.id, changed_by_user_id=None)  # -> DELIVERED
    kitchen_service.advance_dispatch_status(order.id, changed_by_user_id=None)  # -> ARCHIVED

    cards = kitchen_service.list_dispatch_queue()

    assert cards == []


def test_get_pending_dispatch_count_counts_only_pending_orders(kitchen_env: KitchenFixture) -> None:
    """Único método compartido para el contador de despachos pendientes:
    debe contar exclusivamente `OrderStatus.PENDING`, sin incluir
    PREPARING/READY/DELIVERED — a diferencia de `list_dispatch_queue`, que
    sí los incluye para la pantalla de Despacho."""
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()

    pending_order_1 = restaurant_service.create_order(
        table_session_id=None, order_type=OrderType.QUICK, items=[(kitchen_env.product_id, 1, None)]
    )
    restaurant_service.create_order(
        table_session_id=None, order_type=OrderType.QUICK, items=[(kitchen_env.product_id, 1, None)]
    )
    preparing_order = restaurant_service.create_order(
        table_session_id=None, order_type=OrderType.QUICK, items=[(kitchen_env.product_id, 1, None)]
    )
    delivered_order = restaurant_service.create_order(
        table_session_id=None, order_type=OrderType.QUICK, items=[(kitchen_env.product_id, 1, None)]
    )
    kitchen_service.advance_dispatch_status(preparing_order.id, changed_by_user_id=None)
    # delivered_order: dos avances -> PREPARING, luego -> DELIVERED
    kitchen_service.advance_dispatch_status(delivered_order.id, changed_by_user_id=None)
    kitchen_service.advance_dispatch_status(delivered_order.id, changed_by_user_id=None)

    assert kitchen_service.get_pending_dispatch_count() == 2

    kitchen_service.advance_dispatch_status(pending_order_1.id, changed_by_user_id=None)

    assert kitchen_service.get_pending_dispatch_count() == 1


def test_queue_shows_table_name_for_dine_in_orders(kitchen_env: KitchenFixture) -> None:
    restaurant_service = RestaurantService(EventBus())
    kitchen_service = _make_kitchen_service()
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
