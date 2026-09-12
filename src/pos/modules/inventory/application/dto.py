"""DTOs de lectura del módulo de inventario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pos.modules.inventory.domain.enums import StockMovementType, StockStatus


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
class StockSummaryDTO:
    """Existencia total de un producto (suma de todas las bodegas) — una
    fila por producto, para la pantalla principal de Existencias. El
    detalle por bodega se consulta aparte (ver `get_stock_detail`)."""

    product_id: int
    sku: str
    name: str
    total_quantity: Decimal
    min_quantity: Decimal
    status: StockStatus


@dataclass(frozen=True)
class StockMovementDTO:
    id: int
    movement_type: StockMovementType
    quantity: Decimal
    reason: str | None
    created_at: datetime
    product_id: int
    product_name: str
    warehouse_id: int
    warehouse_name: str
    reference_document_type: str | None = None
    reference_document_id: int | None = None
    created_by_user_id: int | None = None
