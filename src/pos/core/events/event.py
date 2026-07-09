"""Clase base de los eventos de dominio despachados por el bus de eventos."""

from __future__ import annotations

import uuid as uuid_lib
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Evento de dominio inmutable.

    Cada módulo define sus propios eventos como subclases (ej.
    `SaleCompletedEvent`, `StockLevelChangedEvent`) en su `domain/events.py`.
    `event_id` y `occurred_at` los genera el bus si no se proveen, para que
    el módulo de Sincronización pueda usarlos como referencia estable.
    """

    event_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
