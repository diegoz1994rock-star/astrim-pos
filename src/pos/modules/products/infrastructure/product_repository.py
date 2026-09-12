"""Acceso a datos de productos, recetas y combos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.products.infrastructure.models import (
    Category,
    Combo,
    ComboItem,
    Product,
    ProductBarcode,
    RecipeItem,
)


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_with_category_name(self) -> list[tuple[Product, str | None]]:
        rows = self._session.execute(
            select(Product, Category.name)
            .outerjoin(Category, Category.id == Product.category_id)
            .options(selectinload(Product.barcodes))
            .where(Product.is_deleted.is_(False))
            .order_by(Product.name)
        )
        return [(row[0], row[1]) for row in rows]

    def list_tracked_active(self) -> list[tuple[Product, str | None]]:
        """Productos activos que controlan inventario — usado por el módulo
        de Inventario para poblar los selectores de Entrada/Salida/Ajuste/
        Transferencia (no tiene sentido registrar movimientos de stock para
        un producto inactivo o que no descuenta inventario)."""
        rows = self._session.execute(
            select(Product, Category.name)
            .outerjoin(Category, Category.id == Product.category_id)
            .options(selectinload(Product.barcodes))
            .where(
                Product.is_deleted.is_(False),
                Product.is_active.is_(True),
                Product.track_inventory.is_(True),
            )
            .order_by(Product.name)
        )
        return [(row[0], row[1]) for row in rows]

    def get_names_by_ids(self, product_ids: list[int]) -> dict[int, str]:
        if not product_ids:
            return {}
        rows = self._session.execute(
            select(Product.id, Product.name).where(Product.id.in_(product_ids))
        )
        return dict(rows.all())

    def get(self, product_id: int) -> Product | None:
        return self._session.get(Product, product_id)

    def get_by_sku(self, sku: str) -> Product | None:
        return self._session.scalar(select(Product).where(Product.sku == sku))

    def get_category_name(self, category_id: int | None) -> str | None:
        if category_id is None:
            return None
        category = self._session.get(Category, category_id)
        return category.name if category is not None else None

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
        image_path: str | None = None,
        sale_unit: SaleUnit = SaleUnit.UNIT,
        min_weight: Decimal | None = None,
        max_weight: Decimal | None = None,
        weight_decimal_places: int | None = None,
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
            image_path=image_path,
            sale_unit=sale_unit,
            min_weight=min_weight,
            max_weight=max_weight,
            weight_decimal_places=weight_decimal_places,
        )
        self._session.add(product)
        self._session.flush()
        return product

    def update(
        self,
        product: Product,
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
        image_path: str | None = None,
        sale_unit: SaleUnit = SaleUnit.UNIT,
        min_weight: Decimal | None = None,
        max_weight: Decimal | None = None,
        weight_decimal_places: int | None = None,
    ) -> None:
        product.sku = sku
        product.name = name
        product.description = description
        product.category_id = category_id
        product.product_type = product_type
        product.unit_price = unit_price
        product.cost_price = cost_price
        product.image_path = image_path
        product.unit_of_measure = unit_of_measure
        product.track_inventory = track_inventory
        product.sale_unit = sale_unit
        product.min_weight = min_weight
        product.max_weight = max_weight
        product.weight_decimal_places = weight_decimal_places
        self._session.flush()

    def set_active(self, product: Product, is_active: bool) -> None:
        product.is_active = is_active

    def has_recipe_or_combo_references(self, product_id: int) -> bool:
        used_in_recipe = (
            self._session.scalar(
                select(RecipeItem.id).where(
                    or_(
                        RecipeItem.recipe_product_id == product_id,
                        RecipeItem.ingredient_product_id == product_id,
                    )
                )
            )
            is not None
        )
        used_as_combo_component = (
            self._session.scalar(select(ComboItem.id).where(ComboItem.product_id == product_id))
            is not None
        )
        is_combo_with_items = (
            self._session.scalar(
                select(ComboItem.id)
                .join(Combo, Combo.id == ComboItem.combo_id)
                .where(Combo.product_id == product_id)
            )
            is not None
        )
        return used_in_recipe or used_as_combo_component or is_combo_with_items

    def delete(self, product: Product) -> None:
        product.is_deleted = True
        product.is_active = False

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

    # -- Códigos de barras ------------------------------------------------

    def list_barcodes(self, product_id: int) -> list[ProductBarcode]:
        return list(
            self._session.scalars(
                select(ProductBarcode)
                .where(ProductBarcode.product_id == product_id)
                .order_by(ProductBarcode.created_at)
            )
        )

    def get_barcode_by_code(self, code: str) -> ProductBarcode | None:
        return self._session.scalar(select(ProductBarcode).where(ProductBarcode.code == code))

    def find_by_barcode(self, code: str) -> Product | None:
        """`SELECT ... JOIN product_barcodes WHERE code = :code`, respaldado
        por el índice único de `ProductBarcode.code` — fuente real que usa
        Ventas al escanear, no una búsqueda lineal."""
        return self._session.scalar(
            select(Product).join(ProductBarcode).where(ProductBarcode.code == code)
        )

    def add_barcode(self, product_id: int, code: str) -> ProductBarcode:
        barcode = ProductBarcode(product_id=product_id, code=code)
        self._session.add(barcode)
        self._session.flush()
        return barcode

    def update_barcode(self, barcode_id: int, code: str) -> ProductBarcode | None:
        barcode = self._session.get(ProductBarcode, barcode_id)
        if barcode is not None:
            barcode.code = code
            self._session.flush()
        return barcode

    def remove_barcode(self, barcode_id: int) -> None:
        barcode = self._session.get(ProductBarcode, barcode_id)
        if barcode is not None:
            self._session.delete(barcode)
