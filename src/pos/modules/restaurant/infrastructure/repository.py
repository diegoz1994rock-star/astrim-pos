"""Acceso a datos de mesas, sesiones de mesa y pedidos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pos.modules.restaurant.domain.enums import (
    OrderItemStatus,
    OrderOrigin,
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
        self,
        *,
        table_session_id: int | None,
        order_type: OrderType,
        created_by_user_id: int | None = None,
        customer_name: str | None = None,
        customer_document: str | None = None,
        origin: OrderOrigin = OrderOrigin.VENDEDOR,
    ) -> Order:
        order = Order(
            table_session_id=table_session_id,
            order_type=order_type,
            created_by_user_id=created_by_user_id,
            customer_name=customer_name,
            customer_document=customer_document,
            origin=origin,
        )
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

    def list_pending_payment_orders(self) -> list[Order]:
        """Pedidos sin cobrar todavía (`sale_id IS NULL`), para "Pedidos
        pendientes de cobro" en Caja — no incluye pedidos anulados."""
        return list(
            self._session.scalars(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.sale_id.is_(None), Order.status != OrderStatus.CANCELLED)
                .order_by(Order.created_at)
            )
        )

    def link_order_to_sale(self, order: Order, sale_id: int) -> None:
        order.sale_id = sale_id

    def get_last_ready_at_by_order(self, order_ids: list[int]) -> dict[int, datetime]:
        """Última vez que un ítem de cada pedido llegó a `READY`, para
        mostrar "Listo: HH:MM" en "Pedidos pendientes de cobro" — una sola
        consulta agregada en vez de una por pedido."""
        if not order_ids:
            return {}
        rows = self._session.execute(
            select(OrderItem.order_id, func.max(OrderItemStatusHistory.changed_at))
            .join(OrderItemStatusHistory, OrderItemStatusHistory.order_item_id == OrderItem.id)
            .where(
                OrderItem.order_id.in_(order_ids),
                OrderItemStatusHistory.status == OrderItemStatus.READY,
            )
            .group_by(OrderItem.order_id)
        ).all()
        return {order_id: changed_at for order_id, changed_at in rows}

    def set_order_status(self, order: Order, status: OrderStatus) -> None:
        order.status = status

    def set_dispatched_by_user(self, order: Order, user_id: int | None) -> None:
        order.dispatched_by_user_id = user_id

    def list_dispatch_queue(self, limit: int = 200) -> list[Order]:
        """Pedidos para la pantalla Despacho, agrupados a nivel de pedido
        (no de ítem) — a diferencia de `list_kitchen_queue`, incluye tanto
        pedidos sin cobrar (Vendedor) como ya cobrados (Ventas, o Vendedor
        ya facturado): el filtrado por pagado/entregado/origen es
        responsabilidad de la vista, no de esta consulta (ver
        `KitchenService.list_dispatch_queue`). `ARCHIVED` se excluye igual
        que `CANCELLED` — es un pedido `DELIVERED` que el cajero ya sacó de
        la cola con "Siguiente proceso"; sigue existiendo, solo deja de
        listarse acá (ver `RestaurantService.advance_dispatch_status`)."""
        return list(
            self._session.scalars(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.ARCHIVED]))
                .order_by(Order.created_at.desc())
                .limit(limit)
            )
        )

    def count_pending_orders(self) -> int:
        """`COUNT` real sobre `orders` en estado `PENDING` únicamente — sin
        traer filas a memoria. Única fuente de verdad para "cuántos
        despachos están pendientes de preparar" (ver
        `KitchenService.get_pending_dispatch_count`); no confundir con
        `list_dispatch_queue`, que trae toda la cola activa (PENDING +
        PREPARING + READY + DELIVERED) para la pantalla de Despacho."""
        return (
            self._session.scalar(
                select(func.count()).select_from(Order).where(Order.status == OrderStatus.PENDING)
            )
            or 0
        )

    def add_order_item(
        self, order: Order, *, product_id: int, quantity: int, notes: str | None
    ) -> OrderItem:
        item = OrderItem(product_id=product_id, quantity=quantity, notes=notes)
        order.items.append(item)
        self._session.flush()
        return item

    # -- Cola de cocina -------------------------------------------------------

    def list_kitchen_queue(self) -> list[OrderItem]:
        """Ítems pendientes de despachar — excluye tanto los ya entregados
        como los de pedidos ya cobrados (`Order.sale_id` no nulo), para que
        pagar un pedido lo saque también de Despacho automáticamente."""
        return list(
            self._session.scalars(
                select(OrderItem)
                .join(Order)
                .where(OrderItem.status != OrderItemStatus.DELIVERED, Order.sale_id.is_(None))
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
