"""Casos de uso de administración de productos, recetas y combos."""

from __future__ import annotations

from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.products.application.dto import ComboItemDTO, ProductDTO, RecipeItemDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.domain.events import ProductCreatedEvent, ProductStatusChangedEvent
from pos.modules.products.infrastructure.models import Product
from pos.modules.products.infrastructure.product_repository import ProductRepository


def _to_dto(repo: ProductRepository, product: Product) -> ProductDTO:
    return ProductDTO(
        id=product.id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        category_id=product.category_id,
        category_name=repo.get_category_name(product.category_id),
        product_type=product.product_type,
        unit_price=product.unit_price,
        cost_price=product.cost_price,
        unit_of_measure=product.unit_of_measure,
        is_active=product.is_active,
        track_inventory=product.track_inventory,
        tax_codes=repo.get_tax_codes(product.id),
    )


class ProductManagementService:
    """CRUD de productos (simples, compuestos y combos), recetas y combos."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_products(self) -> list[ProductDTO]:
        with session_scope() as session:
            repo = ProductRepository(session)
            return [_to_dto(repo, product) for product, _ in repo.list_with_category_name()]

    def list_tax_names(self) -> list[str]:
        with session_scope() as session:
            repo = ProductRepository(session)
            return sorted(tax.name for tax in repo.list_taxes())

    def create_product(
        self,
        *,
        sku: str,
        name: str,
        description: str | None,
        category_id: int | None,
        product_type: ProductType,
        unit_price: Decimal,
        cost_price: Decimal,
        unit_of_measure: str,
        track_inventory: bool,
        tax_codes: set[str],
    ) -> ProductDTO:
        sku = sku.strip()
        name = name.strip()
        if not sku or not name:
            raise BusinessRuleViolationError("El SKU y el nombre del producto son obligatorios.")
        if unit_price < 0 or cost_price < 0:
            raise BusinessRuleViolationError("Los precios no pueden ser negativos.")

        with session_scope() as session:
            repo = ProductRepository(session)
            if repo.get_by_sku(sku) is not None:
                raise ConflictError(f"Ya existe un producto con el SKU '{sku}'.")

            product = repo.create(
                sku=sku,
                name=name,
                description=description,
                category_id=category_id,
                product_type=product_type,
                unit_price=unit_price,
                cost_price=cost_price,
                unit_of_measure=unit_of_measure,
                track_inventory=track_inventory,
            )
            taxes = repo.get_taxes_by_names(tax_codes)
            repo.set_taxes(product, taxes)

            if product_type is ProductType.COMBO:
                repo.get_or_create_combo(product.id)

            dto = _to_dto(repo, product)

        self._event_bus.publish(
            ProductCreatedEvent(
                product_id=dto.id, sku=dto.sku, name=dto.name, track_inventory=dto.track_inventory
            )
        )
        return dto

    def set_active(self, product_id: int, is_active: bool) -> ProductDTO:
        with session_scope() as session:
            repo = ProductRepository(session)
            product = repo.get(product_id)
            if product is None:
                raise NotFoundError(f"No existe el producto con id={product_id}.")
            repo.set_active(product, is_active)
            dto = _to_dto(repo, product)

        self._event_bus.publish(ProductStatusChangedEvent(product_id=dto.id, is_active=is_active))
        return dto

    def add_recipe_item(
        self,
        *,
        recipe_product_id: int,
        ingredient_product_id: int,
        quantity: Decimal,
        unit_of_measure: str,
    ) -> None:
        """Agrega un insumo a la receta de un producto compuesto."""
        if quantity <= 0:
            raise BusinessRuleViolationError("La cantidad del insumo debe ser mayor que cero.")

        with session_scope() as session:
            repo = ProductRepository(session)
            recipe_product = repo.get(recipe_product_id)
            ingredient = repo.get(ingredient_product_id)
            if recipe_product is None or ingredient is None:
                raise NotFoundError("El producto compuesto o el insumo no existen.")
            if recipe_product.product_type is not ProductType.COMPOUND:
                raise BusinessRuleViolationError(
                    "Solo un producto de tipo 'compuesto' puede tener receta."
                )

            repo.add_recipe_item(
                recipe_product_id=recipe_product_id,
                ingredient_product_id=ingredient_product_id,
                quantity=quantity,
                unit_of_measure=unit_of_measure,
            )

    def list_recipe_items(self, recipe_product_id: int) -> list[RecipeItemDTO]:
        with session_scope() as session:
            repo = ProductRepository(session)
            return [
                RecipeItemDTO(
                    id=item.id,
                    ingredient_product_id=item.ingredient_product_id,
                    ingredient_name=name,
                    quantity=item.quantity,
                    unit_of_measure=item.unit_of_measure,
                )
                for item, name in repo.list_recipe_items(recipe_product_id)
            ]

    def add_combo_item(self, *, combo_product_id: int, product_id: int, quantity: Decimal) -> None:
        """Agrega un producto al combo."""
        if quantity <= 0:
            raise BusinessRuleViolationError("La cantidad debe ser mayor que cero.")

        with session_scope() as session:
            repo = ProductRepository(session)
            combo_product = repo.get(combo_product_id)
            component = repo.get(product_id)
            if combo_product is None or component is None:
                raise NotFoundError("El combo o el producto componente no existen.")
            if combo_product.product_type is not ProductType.COMBO:
                raise BusinessRuleViolationError("Solo un producto de tipo 'combo' admite ítems.")

            combo = repo.get_or_create_combo(combo_product_id)
            repo.add_combo_item(combo=combo, product_id=product_id, quantity=quantity)

    def list_combo_items(self, combo_product_id: int) -> list[ComboItemDTO]:
        with session_scope() as session:
            repo = ProductRepository(session)
            combo = repo.get_or_create_combo(combo_product_id)
            return [
                ComboItemDTO(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=name,
                    quantity=item.quantity,
                )
                for item, name in repo.list_combo_items(combo.id)
            ]
