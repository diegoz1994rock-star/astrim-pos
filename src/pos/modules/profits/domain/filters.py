"""Filtros de consulta de Ganancias — estructura pura de dominio,
compartida por `ProfitsService` (application) y `ProfitsRepository`
(infrastructure) para no repetir una lista de 8+ parámetros sueltos en
cada método."""

from __future__ import annotations

from dataclasses import dataclass

from pos.modules.profits.domain.enums import ProfitSortOption


@dataclass(frozen=True)
class ProfitFilters:
    category_id: int | None = None
    supplier_id: int | None = None
    warehouse_id: int | None = None
    user_id: int | None = None
    cash_register_id: int | None = None
    customer_id: int | None = None
    product_code: str | None = None
    product_name: str | None = None
    only_with_profit: bool = False
    only_with_loss: bool = False
    sort: ProfitSortOption = ProfitSortOption.FIRST_SALE_ASC
