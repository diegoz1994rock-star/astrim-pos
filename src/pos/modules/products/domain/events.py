"""Eventos de dominio publicados por el módulo de productos.

`ProductCreatedEvent` es, entre otros, el que el módulo de Inventario
consumirá para crear el `StockLevel` inicial (cantidad 0) de un producto
con `track_inventory=True` en cada bodega — el patrón de referencia para
que otros módulos (Compras, Ventas, Restaurante) se comuniquen entre sí
sin importarse directamente (ver ARCHITECTURE.md §5).
"""

from __future__ import annotations

from dataclasses import dataclass

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ProductCreatedEvent(DomainEvent):
    product_id: int
    sku: str
    name: str
    track_inventory: bool


@dataclass(frozen=True, kw_only=True)
class ProductStatusChangedEvent(DomainEvent):
    product_id: int
    is_active: bool
