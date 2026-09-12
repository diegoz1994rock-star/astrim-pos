"""DTOs de lectura del módulo de productos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos.modules.products.domain.enums import ProductType, SaleUnit


@dataclass(frozen=True)
class CategoryDTO:
    id: int
    name: str
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
    image_path: str | None = None
    sale_unit: SaleUnit = SaleUnit.UNIT
    barcodes: tuple[str, ...] = ()
    """Códigos de barras del producto, en orden de registro (el primero es
    el "primer código registrado" que muestra Catálogo/Inventario)."""
    min_weight: Decimal | None = None
    max_weight: Decimal | None = None
    weight_decimal_places: int | None = None


@dataclass(frozen=True)
class ProductBarcodeDTO:
    id: int
    code: str


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
