"""DTOs de lectura del módulo de productos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos.modules.products.domain.enums import ProductType


@dataclass(frozen=True)
class CategoryDTO:
    id: int
    name: str
    parent_id: int | None
    parent_name: str | None
    is_active: bool


@dataclass(frozen=True)
class ProductDTO:
    id: int
    sku: str
    name: str
    description: str | None
    category_id: int | None
    category_name: str | None
    product_type: ProductType
    unit_price: Decimal
    cost_price: Decimal
    unit_of_measure: str
    is_active: bool
    track_inventory: bool
    tax_codes: frozenset[str]


@dataclass(frozen=True)
class RecipeItemDTO:
    id: int
    ingredient_product_id: int
    ingredient_name: str
    quantity: Decimal
    unit_of_measure: str


@dataclass(frozen=True)
class ComboItemDTO:
    id: int
    product_id: int
    product_name: str
    quantity: Decimal
