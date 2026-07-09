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


class OrderItemStatus(enum.Enum):
    """Estado de un ítem de pedido en cocina (PROJECT_SPEC.md, "COCINA")."""

    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
