"""DTOs del módulo de Restaurante (mesas y pedidos)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.restaurant.domain.enums import (
    OrderItemStatus,
    OrderStatus,
    OrderType,
    TableSessionStatus,
    TableStatus,
)


@dataclass(frozen=True)
class DiningTableDTO:
    id: int
    name: str
    capacity: int
    zone: str | None
    status: TableStatus


@dataclass(frozen=True)
class TableSessionDTO:
    id: int
    table_id: int
    waiter_user_id: int
    status: TableSessionStatus
    opened_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True)
class OrderItemDTO:
    id: int
    order_id: int
    product_id: int
    product_name: str
    quantity: int
    notes: str | None
    status: OrderItemStatus


@dataclass(frozen=True)
class OrderDTO:
    id: int
    table_session_id: int | None
    order_type: OrderType
    status: OrderStatus
    items: list[OrderItemDTO]


@dataclass(frozen=True)
class KitchenQueueItemDTO:
    """Ítem de pedido visto desde la pantalla de cocina, con el contexto
    que un cocinero necesita (mesa/tipo de pedido) sin tener que consultar
    el módulo de Restaurante aparte."""

    order_item_id: int
    order_id: int
    product_id: int
    product_name: str
    quantity: int
    notes: str | None
    status: OrderItemStatus
    order_type: OrderType
    table_name: str | None
