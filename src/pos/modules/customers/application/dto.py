"""DTOs de lectura del módulo de clientes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CustomerDTO:
    id: int
    full_name: str
    document_id: str | None
    email: str | None
    phone: str | None
    address: str | None
    credit_limit: Decimal
    current_debt: Decimal
    loyalty_points_balance: int
