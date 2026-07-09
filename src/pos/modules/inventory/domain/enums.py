"""Enumeraciones de dominio del módulo de inventario."""

from __future__ import annotations

import enum


class StockMovementType(enum.Enum):
    """Tipo de movimiento de inventario (PROJECT_SPEC.md, "INVENTARIO")."""

    ENTRY = "entry"
    EXIT = "exit"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
