"""Enumeraciones de dominio del módulo de restaurante (mesas y pedidos)."""

from __future__ import annotations

import enum


class TableStatus(enum.Enum):
    """Estado de una mesa."""

    FREE = "free"
    OCCUPIED = "occupied"
    RESERVED = "reserved"


class TableSessionStatus(enum.Enum):
    """Estado de una ocupación de mesa (desde que se sienta el cliente
    hasta que se cierra la cuenta)."""

    OPEN = "open"
    CLOSED = "closed"


class OrderType(enum.Enum):
    """Origen/canal del pedido (PROJECT_SPEC.md, "RESTAURANTES")."""

    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"
    QUICK = "quick"


class OrderStatus(enum.Enum):
    """Estado del pedido en su conjunto."""

    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"
    """Pedido ya entregado y confirmado desde Despacho ("Siguiente proceso"
    presionado sobre un pedido `DELIVERED`) — deja de listarse en la cola
    de Despacho (ver `RestaurantRepository.list_dispatch_queue`), igual
    que `CANCELLED`, pero el registro se conserva íntegro para venta/
    factura/historial/auditoría."""


class OrderItemStatus(enum.Enum):
    """Estado de un ítem de pedido en cocina (PROJECT_SPEC.md, "COCINA")."""

    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"


class OrderOrigin(enum.Enum):
    """Cómo se creó el pedido — dato de trazabilidad fijo, independiente del
    estado de pago (que se deriva en vivo de `Order.sale_id`, ver
    `RestaurantService.list_dispatch_queue`)."""

    VENDEDOR = "vendedor"
    """Tomado desde la pantalla Vendedor, sin cobrar todavía al crearse."""
    VENTAS = "ventas"
    """Creado automáticamente al completar una venta directo en Ventas, sin
    pasar por un pedido de Vendedor — nace ya cobrado."""
