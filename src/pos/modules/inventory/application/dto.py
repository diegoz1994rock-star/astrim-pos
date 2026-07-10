"""DTOs de lectura del módulo de inventario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pos.modules.inventory.domain.enums import StockMovementType


@dataclass(frozen=True)
class WarehouseDTO:
    id: int
    name: str
    location: str | None
    is_active: bool


@dataclass(frozen=True)
class StockLevelDTO:
    product_id: int
    product_name: str
    product_sku: str
    warehouse_id: int
    warehouse_name: str
    quantity: Decimal
    min_quantity: Decimal
    is_below_minimum: bool


@dataclass(frozen=True)
class StockMovementDTO:
    id: int
    movement_type: StockMovementType
    quantity: Decimal
    reason: str | None
    created_at: datetime
