"""Eventos de dominio publicados por el módulo de ventas.

Se publican **después** de que la venta y todos sus efectos críticos
(descuento de stock, movimiento de caja, cargo a crédito) ya se aplicaron
con éxito — ver ARCHITECTURE.md §5b. Solo para consumidores de solo lectura
(Auditoría, Reportes, Notificaciones, Sincronización).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class SaleCompletedEvent(DomainEvent):
    sale_id: int
    total: Decimal
    customer_id: int | None


@dataclass(frozen=True, kw_only=True)
class SaleVoidedEvent(DomainEvent):
    sale_id: int
    reason: str | None
