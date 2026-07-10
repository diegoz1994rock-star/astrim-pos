"""DTOs de lectura del módulo de reportes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class SalesReportRowDTO:
    sale_id: int
    created_at: datetime
    status: str
    customer_name: str
    total: Decimal


@dataclass(frozen=True)
class SalesReportDTO:
    date_from: date
    date_to: date
    rows: list[SalesReportRowDTO] = field(default_factory=list)
    total_amount: Decimal = Decimal(0)
    total_count: int = 0


@dataclass(frozen=True)
class InventoryReportRowDTO:
    sku: str
    product_name: str
    warehouse_name: str
    quantity: Decimal
    min_quantity: Decimal
    is_below_minimum: bool


@dataclass(frozen=True)
class InventoryReportDTO:
    rows: list[InventoryReportRowDTO] = field(default_factory=list)


@dataclass(frozen=True)
class CashReportRowDTO:
    session_id: int
    register_name: str
    opened_at: datetime
    closed_at: datetime | None
    opening_amount: Decimal
    closing_amount: Decimal | None
    expected_amount: Decimal | None
    difference: Decimal | None


@dataclass(frozen=True)
class CashReportDTO:
    rows: list[CashReportRowDTO] = field(default_factory=list)


@dataclass(frozen=True)
class ProductSalesRowDTO:
    """Fila del reporte de productos: unidades y monto vendido en el período."""

    sku: str
    product_name: str
    quantity_sold: Decimal
    revenue: Decimal


@dataclass(frozen=True)
class ProductSalesReportDTO:
    date_from: date
    date_to: date
    rows: list[ProductSalesRowDTO] = field(default_factory=list)
