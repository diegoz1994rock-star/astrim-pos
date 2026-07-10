"""DTOs de lectura del módulo de caja."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pos.modules.cash_register.domain.enums import CashMovementType, CashSessionStatus


@dataclass(frozen=True)
class CashRegisterDTO:
    id: int
    name: str
    location: str | None
    is_active: bool


@dataclass(frozen=True)
class CashSessionDTO:
    id: int
    cash_register_id: int
    cash_register_name: str
    status: CashSessionStatus
    opened_by_user_id: int
    opened_at: datetime
    opening_amount: Decimal
    closed_at: datetime | None
    closing_amount: Decimal | None
    expected_amount: Decimal | None
    difference: Decimal | None


@dataclass(frozen=True)
class CashMovementDTO:
    id: int
    movement_type: CashMovementType
    amount: Decimal
    reason: str | None
    created_at: datetime
