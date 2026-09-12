"""DTOs del módulo de Ganancias — capa de aplicación."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_
from datetime import datetime
from decimal import Decimal

from pos.modules.products.domain.enums import SaleUnit


@dataclass(frozen=True)
class ProfitSummaryDTO:
    total_revenue: Decimal
    total_quantity: Decimal
    invoice_count: int
    total_cost: Decimal | None
    total_profit: Decimal | None
    avg_margin_pct: Decimal | None
    has_missing_cost: bool = False


@dataclass(frozen=True)
class ProductProfitRowDTO:
    product_id: int
    code: str
    category_name: str
    product_name: str
    sale_unit: SaleUnit
    quantity_sold: Decimal
    avg_purchase_price: Decimal | None
    avg_sale_price: Decimal
    total_cost: Decimal | None
    total_revenue: Decimal
    total_profit: Decimal | None
    margin_pct: Decimal | None
    invoice_count: int
    first_sale_at: datetime
    last_sale_at: datetime
    current_stock: Decimal
    supplier_name: str
    top_seller_name: str
    missing_cost: bool = False
    min_sale_price: Decimal | None = None
    max_sale_price: Decimal | None = None
    avg_profit_per_unit: Decimal | None = None


@dataclass(frozen=True)
class CategoryProfitGroupDTO:
    category_id: int | None
    category_name: str
    quantity_sold: Decimal
    total_revenue: Decimal
    total_cost: Decimal | None
    total_profit: Decimal | None
    missing_cost: bool = False


@dataclass(frozen=True)
class TopListEntryDTO:
    product_id: int
    label: str
    value: Decimal


@dataclass(frozen=True)
class TopListsDTO:
    highest_profit: list[TopListEntryDTO] = field(default_factory=list)
    lowest_profit: list[TopListEntryDTO] = field(default_factory=list)
    most_sold: list[TopListEntryDTO] = field(default_factory=list)
    least_sold: list[TopListEntryDTO] = field(default_factory=list)
    highest_revenue: list[TopListEntryDTO] = field(default_factory=list)
    lowest_revenue: list[TopListEntryDTO] = field(default_factory=list)


@dataclass(frozen=True)
class ChartSeriesDTO:
    top_products_by_quantity: list[TopListEntryDTO]
    profit_by_category: list[CategoryProfitGroupDTO]
    """Ingreso Y ganancia por categoría — `CategoryProfitGroupDTO` completo
    (no `TopListEntryDTO`, que solo tiene un valor) porque la gráfica de
    barras muestra ambas cifras por categoría, no una sola."""
    daily_revenue: list[tuple[date_, Decimal]]
    cumulative_profit: list[tuple[date_, Decimal]]


@dataclass(frozen=True)
class ProductSaleHistoryEntryDTO:
    sale_id: int
    invoice_number: str | None
    customer_name: str
    user_name: str
    cash_register_name: str
    sold_at: datetime
    quantity: Decimal
    unit_cost: Decimal | None
    unit_price: Decimal
    line_profit: Decimal | None
    sale_unit: SaleUnit
