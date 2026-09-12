"""DTOs del módulo de Restaurante (mesas y pedidos)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.restaurant.domain.enums import (
    OrderItemStatus,
    OrderOrigin,
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
    product_image_path: str | None = None


@dataclass(frozen=True)
class OrderDTO:
    id: int
    table_session_id: int | None
    order_type: OrderType
    status: OrderStatus
    items: list[OrderItemDTO]
    created_at: datetime | None = None
    created_by_user_id: int | None = None
    sale_id: int | None = None
    customer_name: str | None = None
    customer_document: str | None = None
    origin: OrderOrigin = OrderOrigin.VENDEDOR
    dispatched_by_user_id: int | None = None
    ready_at: datetime | None = None
    """Última vez que algún ítem del pedido llegó a `READY` — se completa
    solo en `RestaurantService.list_pending_payment_orders` (ver
    `RestaurantRepository.get_last_ready_at_by_order`), para mostrar
    "Listo: HH:MM" en "Pedidos pendientes de cobro"."""


@dataclass(frozen=True)
class KitchenQueueItemDTO:
    """Ítem de pedido visto desde la pantalla de Despacho, con el contexto
    que el encargado necesita (empleado/hora/tipo de pedido) sin tener que
    consultar el módulo de Restaurante aparte."""

    order_item_id: int
    order_id: int
    product_id: int
    product_name: str
    quantity: int
    notes: str | None
    status: OrderItemStatus
    order_type: OrderType
    table_name: str | None
    product_image_path: str | None = None
    created_at: datetime | None = None
    created_by_user_name: str | None = None
    customer_name: str | None = None


@dataclass(frozen=True)
class DispatchOrderCardDTO:
    """Un pedido/venta completo visto como tarjeta de cliente en Despacho
    (`KitchenService.list_dispatch_queue`) — reemplaza la vista anterior de
    ítems sueltos. `is_paid`/`caja_name` se resuelven en vivo a partir de si
    el pedido ya tiene una venta asociada, nunca a partir de `origin` (que
    es solo trazabilidad de cómo se creó, ver `OrderOrigin`)."""

    order_id: int
    origin: OrderOrigin
    customer_name: str
    customer_document: str | None
    is_paid: bool
    caja_name: str | None
    """`None` = pedido sin cobrar todavía ("Sin caja asignada" en la
    vista); una vez cobrado, el nombre real de la caja donde se pagó."""
    dispatch_status: OrderStatus
    item_count: int
    total_units: int
    items: list[OrderItemDTO]
    created_at: datetime | None = None
    created_by_user_name: str | None = None
    dispatched_by_user_name: str | None = None
    sale_id: int | None = None
    """Mismo valor que ya resuelve `is_paid` (`order.sale_id is not None`)
    — expuesto acá tal cual para que un cliente remoto pueda consultar el
    precio/pago real de un pedido ya cobrado vía `GET /sales/{sale_id}`
    (Fase 4/6 de la API), sin duplicar esa consulta ni su cálculo."""
