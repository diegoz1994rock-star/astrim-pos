"""Eventos de dominio publicados por el módulo de caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class CashSessionOpenedEvent(DomainEvent):
    cash_session_id: int
    cash_register_id: int


@dataclass(frozen=True, kw_only=True)
class CashSessionClosedEvent(DomainEvent):
    """Se publica al cerrar un turno de caja; consumido por Reportes y
    Auditoría. `difference` distinto de cero indica descuadre del arqueo."""

    cash_session_id: int
    difference: Decimal
