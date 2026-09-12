"""Eventos de dominio publicados por el módulo de Restaurante (Vendedor).

Se publica **después** de persistir el pedido, para que Despacho y Caja se
enteren de inmediato (ver `notifications`, `kitchen`) sin que Restaurante
tenga que conocer a sus consumidores."""

from __future__ import annotations

from dataclasses import dataclass

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class OrderCreatedEvent(DomainEvent):
    order_id: int
    created_by_user_id: int | None = None
