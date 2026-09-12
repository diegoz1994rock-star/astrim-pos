"""Modelos Pydantic de la API de consulta de Productos (Fase 2) — mismo
principio que `schemas.py` de Auth: traducen los DTOs ya existentes de
`modules.products.application.dto` a la forma JSON pública, sin exponer
`ProductDTO.cost_price` a propósito. El costo es dato de margen que ni
siquiera la pantalla de Ventas del escritorio muestra — solo aparece en el
formulario de administración de Catálogo (`product_form_dialog.py`), al que
esta API de solo-consulta no da ningún acceso equivalente."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from pos.modules.products.application.dto import (
    CategoryDTO,
    ComboItemDTO,
    ProductDTO,
    RecipeItemDTO,
)


class CategorySchema(BaseModel):
    id: int
    name: str
    is_active: bool

    @classmethod
    def from_dto(cls, dto: CategoryDTO) -> CategorySchema:
        return cls(id=dto.id, name=dto.name, is_active=dto.is_active)


class RecipeItemSchema(BaseModel):
    ingredient_product_id: int
    ingredient_name: str
    quantity: Decimal
    unit_of_measure: str

    @classmethod
    def from_dto(cls, dto: RecipeItemDTO) -> RecipeItemSchema:
        return cls(
            ingredient_product_id=dto.ingredient_product_id,
            ingredient_name=dto.ingredient_name,
            quantity=dto.quantity,
            unit_of_measure=dto.unit_of_measure,
        )


class ComboItemSchema(BaseModel):
    product_id: int
    product_name: str
    quantity: Decimal

    @classmethod
    def from_dto(cls, dto: ComboItemDTO) -> ComboItemSchema:
        return cls(product_id=dto.product_id, product_name=dto.product_name, quantity=dto.quantity)


class ProductSummary(BaseModel):
    """Forma liviana usada en listado/búsqueda (`GET /products`) — sin
    `description` ni receta/combo, que solo importan al consultar un
    producto puntual (ver `ProductDetail`)."""

    id: int
    sku: str
    name: str
    category_id: int | None
    category_name: str | None
    product_type: str
    unit_price: Decimal
    unit_of_measure: str
    sale_unit: str
    is_active: bool
    track_inventory: bool
    image_path: str | None
    barcodes: list[str]

    @classmethod
    def from_dto(cls, dto: ProductDTO) -> ProductSummary:
        return cls(
            id=dto.id,
            sku=dto.sku,
            name=dto.name,
            category_id=dto.category_id,
            category_name=dto.category_name,
            product_type=dto.product_type.value,
            unit_price=dto.unit_price,
            unit_of_measure=dto.unit_of_measure,
            sale_unit=dto.sale_unit.value,
            is_active=dto.is_active,
            track_inventory=dto.track_inventory,
            image_path=dto.image_path,
            barcodes=list(dto.barcodes),
        )


class ProductDetail(ProductSummary):
    """Todo lo de `ProductSummary` más lo que solo tiene sentido al abrir un
    producto puntual: descripción, rango de peso (solo aplica si
    `sale_unit == "weight"`) y receta/combo (solo aplica según
    `product_type` — listas vacías en cualquier otro caso, nunca `None`,
    para que el cliente no tenga que distinguir "no aplica" de "no tiene
    ítems")."""

    description: str | None
    min_weight: Decimal | None
    max_weight: Decimal | None
    weight_decimal_places: int | None
    recipe_items: list[RecipeItemSchema] = []
    combo_items: list[ComboItemSchema] = []

    @classmethod
    def from_dto(
        cls,
        dto: ProductDTO,
        *,
        recipe_items: list[RecipeItemDTO] | None = None,
        combo_items: list[ComboItemDTO] | None = None,
    ) -> ProductDetail:
        summary = ProductSummary.from_dto(dto)
        return cls(
            **summary.model_dump(),
            description=dto.description,
            min_weight=dto.min_weight,
            max_weight=dto.max_weight,
            weight_decimal_places=dto.weight_decimal_places,
            recipe_items=[RecipeItemSchema.from_dto(r) for r in recipe_items or []],
            combo_items=[ComboItemSchema.from_dto(c) for c in combo_items or []],
        )
