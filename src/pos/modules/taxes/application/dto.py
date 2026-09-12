"""DTOs del módulo de Impuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TaxDTO:
    id: int
    name: str
    rate_percent: Decimal
    is_active: bool
