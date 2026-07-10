"""Acceso a datos de productos, recetas y combos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from pos.modules.products.domain.enums import ProductType
from pos.modules.products.infrastructure.models import (
    Category,
    Combo,
    ComboItem,
    Product,
    ProductTax,
    RecipeItem,
    Tax,
)


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_with_category_name(self) -> list[tuple[Product, str | None]]:
        rows = self._session.execute(
            select(Product, Category.name)
            .outerjoin(Category, Category.id == Product.category_id)
            .where(Product.is_deleted.is_(False))
            .order_by(Product.name)
        )
        return [(row[0], row[1]) for row in rows]

    def get(self, product_id: int) -> Product | None:
        return self._session.get(Product, product_id)

    def get_by_sku(self, sku: str) -> Product | None:
        return self._session.scalar(select(Product).where(Product.sku == sku))

    def get_category_name(self, category_id: int | None) -> str | None:
        if category_id is None:
            return None
        category = self._session.get(Category, category_id)
        return category.name if category is not None else None

    def list_taxes(self) -> list[Tax]:
        return list(self._session.scalars(select(Tax).where(Tax.is_active.is_(True))))

    def get_taxes_for_product(self, product_id: int) -> list[Tax]:
        """Tasas de impuesto asignadas a un producto, usado por Ventas para
        calcular `tax_amount` de cada línea (no solo sus nombres)."""
        return list(
            self._session.scalars(
                select(Tax)
                .join(ProductTax, ProductTax.tax_id == Tax.id)
                .where(ProductTax.product_id == product_id)
            )
        )

    def get_tax_codes(self, product_id: int) -> frozenset[str]:
        rows = self._session.execute(
            select(Tax.name)
            .join(ProductTax, ProductTax.tax_id == Tax.id)
            .where(ProductTax.product_id == product_id)
        )
        return frozenset(row[0] for row in rows)

    def create(
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
    ) -> Product:
        product = Product(
            sku=sku,
            name=name,
            description=description,
            category_id=category_id,
            product_type=product_type,
            unit_price=unit_price,
            cost_price=cost_price,
            unit_of_measure=unit_of_measure,
            is_active=True,
            track_inventory=track_inventory,
        )
        self._session.add(product)
        self._session.flush()
        return product

    def set_taxes(self, product: Product, taxes: list[Tax]) -> None:
        self._session.query(ProductTax).filter(ProductTax.product_id == product.id).delete()
        for tax in taxes:
            self._session.add(ProductTax(product_id=product.id, tax_id=tax.id))
        self._session.flush()

    def get_taxes_by_names(self, names: set[str]) -> list[Tax]:
        if not names:
            return []
        return list(self._session.scalars(select(Tax).where(Tax.name.in_(names))))

    def set_active(self, product: Product, is_active: bool) -> None:
        product.is_active = is_active

    def add_recipe_item(
        self,
        *,
        recipe_product_id: int,
        ingredient_product_id: int,
        quantity: Decimal,
        unit_of_measure: str,
    ) -> RecipeItem:
        item = RecipeItem(
            recipe_product_id=recipe_product_id,
            ingredient_product_id=ingredient_product_id,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def list_recipe_items(self, recipe_product_id: int) -> list[tuple[RecipeItem, str]]:
        ingredient = aliased(Product)
        rows = self._session.execute(
            select(RecipeItem, ingredient.name)
            .join(ingredient, ingredient.id == RecipeItem.ingredient_product_id)
            .where(RecipeItem.recipe_product_id == recipe_product_id)
        )
        return [(row[0], row[1]) for row in rows]

    def get_or_create_combo(self, product_id: int) -> Combo:
        combo = self._session.scalar(select(Combo).where(Combo.product_id == product_id))
        if combo is None:
            combo = Combo(product_id=product_id)
            self._session.add(combo)
            self._session.flush()
        return combo

    def add_combo_item(self, *, combo: Combo, product_id: int, quantity: Decimal) -> ComboItem:
        item = ComboItem(combo_id=combo.id, product_id=product_id, quantity=quantity)
        self._session.add(item)
        self._session.flush()
        return item

    def list_combo_items(self, combo_id: int) -> list[tuple[ComboItem, str]]:
        component = aliased(Product)
        rows = self._session.execute(
            select(ComboItem, component.name)
            .join(component, component.id == ComboItem.product_id)
            .where(ComboItem.combo_id == combo_id)
        )
        return [(row[0], row[1]) for row in rows]
