"""Acceso a datos de mesas, sesiones de mesa y pedidos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pos.modules.restaurant.domain.enums import (
    OrderItemStatus,
    OrderStatus,
    OrderType,
    TableSessionStatus,
    TableStatus,
)
from pos.modules.restaurant.infrastructure.models import (
    DiningTable,
    Order,
    OrderItem,
    OrderItemStatusHistory,
    TableSession,
)


class RestaurantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- Mesas ------------------------------------------------------------

    def list_tables(self) -> list[DiningTable]:
        return list(self._session.scalars(select(DiningTable).order_by(DiningTable.name)))

    def get_table(self, table_id: int) -> DiningTable | None:
        return self._session.get(DiningTable, table_id)

    def create_table(self, *, name: str, capacity: int, zone: str | None) -> DiningTable:
        table = DiningTable(name=name, capacity=capacity, zone=zone, status=TableStatus.FREE)
        self._session.add(table)
        self._session.flush()
        return table

    def set_table_status(self, table: DiningTable, status: TableStatus) -> None:
        table.status = status

    # -- Sesiones de mesa ---------------------------------------------------

    def get_session(self, session_id: int) -> TableSession | None:
        return self._session.get(TableSession, session_id)

    def get_open_session_for_table(self, table_id: int) -> TableSession | None:
        return self._session.scalar(
            select(TableSession).where(
                TableSession.table_id == table_id,
                TableSession.status == TableSessionStatus.OPEN,
            )
        )

    def create_session(self, *, table_id: int, waiter_user_id: int) -> TableSession:
        table_session = TableSession(table_id=table_id, waiter_user_id=waiter_user_id)
        self._session.add(table_session)
        self._session.flush()
        return table_session

    def close_session(self, table_session: TableSession, *, closed_at: datetime) -> None:
        table_session.status = TableSessionStatus.CLOSED
        table_session.closed_at = closed_at

    def list_open_sessions(self) -> list[TableSession]:
        return list(
            self._session.scalars(
                select(TableSession).where(TableSession.status == TableSessionStatus.OPEN)
            )
        )

    # -- Pedidos ------------------------------------------------------------

    def create_order(
        self, *, table_session_id: int | None, order_type: OrderType
    ) -> Order:
        order = Order(table_session_id=table_session_id, order_type=order_type)
        self._session.add(order)
        self._session.flush()
        return order

    def get_order(self, order_id: int) -> Order | None:
        return self._session.scalar(
            select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
        )

    def list_orders_for_session(self, table_session_id: int) -> list[Order]:
        return list(
            self._session.scalars(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.table_session_id == table_session_id)
            )
        )

    def set_order_status(self, order: Order, status: OrderStatus) -> None:
        order.status = status

    def add_order_item(
        self, order: Order, *, product_id: int, quantity: int, notes: str | None
    ) -> OrderItem:
        item = OrderItem(product_id=product_id, quantity=quantity, notes=notes)
        order.items.append(item)
        self._session.flush()
        return item

    # -- Cola de cocina -------------------------------------------------------

    def list_kitchen_queue(self) -> list[OrderItem]:
        return list(
            self._session.scalars(
                select(OrderItem)
                .where(OrderItem.status != OrderItemStatus.DELIVERED)
                .order_by(OrderItem.id)
            )
        )

    def get_order_item(self, order_item_id: int) -> OrderItem | None:
        return self._session.get(OrderItem, order_item_id)

    def set_order_item_status(
        self,
        item: OrderItem,
        *,
        status: OrderItemStatus,
        changed_at: datetime,
        changed_by_user_id: int | None,
    ) -> None:
        item.status = status
        self._session.add(
            OrderItemStatusHistory(
                order_item_id=item.id,
                status=status,
                changed_at=changed_at,
                changed_by_user_id=changed_by_user_id,
            )
        )
