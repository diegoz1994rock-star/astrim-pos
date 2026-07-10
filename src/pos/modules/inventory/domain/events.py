"""Eventos de dominio publicados por el módulo de inventario."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class StockLevelChangedEvent(DomainEvent):
    """El stock de un producto en una bodega cambió. Lo consumirán, entre
    otros, Notificaciones (alerta de stock bajo/agotado) y Reportes."""

    product_id: int
    warehouse_id: int
    new_quantity: Decimal
    is_below_minimum: bool
