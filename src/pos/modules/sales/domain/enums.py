"""Enumeraciones de dominio del módulo de ventas."""

from __future__ import annotations

import enum


class SaleStatus(enum.Enum):
    """Estado del ciclo de vida de una venta."""

    DRAFT = "draft"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class SaleType(enum.Enum):
    """Canal/origen de la venta."""

    COUNTER = "counter"
    """Venta directa en mostrador (comercio no-restaurante)."""
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"
    QUICK = "quick"


class PaymentMethod(enum.Enum):
    """Medio de pago de una venta. Una venta puede combinar varios (pago mixto)."""

    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CUSTOMER_CREDIT = "customer_credit"
    OTHER = "other"
