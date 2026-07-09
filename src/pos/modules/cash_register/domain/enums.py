"""Enumeraciones de dominio del módulo de caja."""

from __future__ import annotations

import enum


class CashSessionStatus(enum.Enum):
    """Estado de una sesión de caja (turno de apertura/cierre)."""

    OPEN = "open"
    CLOSED = "closed"


class CashMovementType(enum.Enum):
    """Tipo de movimiento de efectivo dentro de una sesión de caja."""

    SALE = "sale"
    MANUAL_IN = "manual_in"
    MANUAL_OUT = "manual_out"
    REFUND = "refund"
