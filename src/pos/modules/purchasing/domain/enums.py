"""Enumeraciones de dominio del módulo de compras."""

from __future__ import annotations

import enum


class PurchaseOrderStatus(enum.Enum):
    """Estado de una orden de compra a proveedor."""

    DRAFT = "draft"
    SENT = "sent"
    RECEIVED = "received"
    CANCELLED = "cancelled"
