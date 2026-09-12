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
    """Medio de pago de una venta. Una venta puede combinar varios (pago mixto).

    Solo CASH/CARD/QR/NEQUI/BRE_B se ofrecen en la pantalla de Ventas (ver
    `sale_view.py::_SELECTABLE_PAYMENT_METHODS`). TRANSFER/DAVIPLATA/
    CUSTOMER_CREDIT/OTHER se conservan sin eliminar/renombrar únicamente
    para no invalidar el medio de pago de ventas históricas ya guardadas
    con esos valores. El cobro por QR/NEQUI/BRE_B es completamente manual
    (ver módulos `qr_payments`/`nequi_payments`/`bre_b_payments`) — no hay
    integración bancaria automática."""

    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    NEQUI = "nequi"
    DAVIPLATA = "daviplata"
    QR = "qr"
    BRE_B = "bre_b"
    CUSTOMER_CREDIT = "customer_credit"
    OTHER = "other"
