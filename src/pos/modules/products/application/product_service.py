"""Casos de uso de administración de productos, recetas y combos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.products.application.dto import (
    ComboItemDTO,
    ProductBarcodeDTO,
    ProductDTO,
    RecipeItemDTO,
)
from pos.modules.products.domain.barcode_generation import generate_ean13_candidate
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.products.domain.events import ProductCreatedEvent, ProductStatusChangedEvent
from pos.modules.products.infrastructure.models import Product
from pos.modules.products.infrastructure.product_repository import ProductRepository

_MAX_BARCODE_GENERATION_ATTEMPTS = 20
MAX_BARCODE_LENGTH = 64
"""Igual al límite de la columna `product_barcodes.code` (`String(64)`).
SQLite no aplica ese límite por sí solo (a diferencia de Postgres/MySQL,
`VARCHAR(N)` en SQLite es solo una afinidad de tipo, no una restricción
real) — comprobado insertando una cadena de 400 caracteres sin error. Sin
esta validación, un lector mal configurado que envíe basura larga podría
guardarse silenciosamente sin límite."""


def _barcode_owner_label(repo: ProductRepository, product_id: int) -> str:
    owner = repo.get(product_id)
    return f"{owner.name} (SKU {owner.sku})" if owner is not None else "otro producto"


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
        image_path=product.image_path,
        sale_unit=product.sale_unit,
        barcodes=tuple(b.code for b in product.barcodes),
        min_weight=product.min_weight,
        max_weight=product.max_weight,
        weight_decimal_places=product.weight_decimal_places,
    )


def _validate_weight_range(
    sale_unit: SaleUnit,
    min_weight: Decimal | None,
    max_weight: Decimal | None,
    weight_decimal_places: int | None,
) -> None:
    """Peso mínimo/máximo/decimales solo tienen sentido en productos por
    peso — un producto por unidad con estos campos sería una opción
    decorativa sin efecto real, así que se rechaza en vez de ignorarse en
    silencio."""
    if sale_unit is not SaleUnit.WEIGHT:
        if min_weight is not None or max_weight is not None or weight_decimal_places is not None:
            raise BusinessRuleViolationError(
                "Peso mínimo/máximo/decimales solo aplican a productos con tipo de venta "
                "'Peso'."
            )
        return
    if min_weight is not None and min_weight < 0:
        raise BusinessRuleViolationError("El peso mínimo no puede ser negativo.")
    if max_weight is not None and max_weight < 0:
        raise BusinessRuleViolationError("El peso máximo no puede ser negativo.")
    if min_weight is not None and max_weight is not None and max_weight <= min_weight:
        raise BusinessRuleViolationError("El peso máximo debe ser mayor al peso mínimo.")
    if weight_decimal_places is not None and not (0 <= weight_decimal_places <= 4):
        raise BusinessRuleViolationError("Los decimales de peso deben estar entre 0 y 4.")


class ProductManagementService:
    """CRUD de productos (simples, compuestos y combos), recetas y combos."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_products(self) -> list[ProductDTO]:
        with session_scope() as session:
            repo = ProductRepository(session)
            return [_to_dto(repo, product) for product, _ in repo.list_with_category_name()]

    def list_products_for_inventory(self) -> list[ProductDTO]:
        with session_scope() as session:
            repo = ProductRepository(session)
            return [_to_dto(repo, product) for product, _ in repo.list_tracked_active()]

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
        image_path: str | None = None,
        sale_unit: SaleUnit = SaleUnit.UNIT,
        min_weight: Decimal | None = None,
        max_weight: Decimal | None = None,
        weight_decimal_places: int | None = None,
    ) -> ProductDTO:
        sku = sku.strip()
        name = name.strip()
        if not sku or not name:
            raise BusinessRuleViolationError("El SKU y el nombre del producto son obligatorios.")
        if unit_price < 0 or cost_price < 0:
            raise BusinessRuleViolationError("Los precios no pueden ser negativos.")
        _validate_weight_range(sale_unit, min_weight, max_weight, weight_decimal_places)

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
                image_path=image_path,
                sale_unit=sale_unit,
                min_weight=min_weight,
                max_weight=max_weight,
                weight_decimal_places=weight_decimal_places,
            )

            if product_type is ProductType.COMBO:
                repo.get_or_create_combo(product.id)

            dto = _to_dto(repo, product)

        self._event_bus.publish(
            ProductCreatedEvent(
                product_id=dto.id, sku=dto.sku, name=dto.name, track_inventory=dto.track_inventory
            )
        )
        return dto

    def update_product(
        self,
        product_id: int,
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
    ) -> ProductDTO:
        sku = sku.strip()
        name = name.strip()
        if not sku or not name:
            raise BusinessRuleViolationError("El SKU y el nombre del producto son obligatorios.")
        if unit_price < 0 or cost_price < 0:
            raise BusinessRuleViolationError("Los precios no pueden ser negativos.")
        _validate_weight_range(sale_unit, min_weight, max_weight, weight_decimal_places)

        with session_scope() as session:
            repo = ProductRepository(session)
            product = repo.get(product_id)
            if product is None:
                raise NotFoundError(f"No existe el producto con id={product_id}.")

            existing = repo.get_by_sku(sku)
            if existing is not None and existing.id != product_id:
                raise ConflictError(f"Ya existe un producto con el SKU '{sku}'.")

            if image_path is None:
                image_path = product.image_path

            repo.update(
                product,
                sku=sku,
                name=name,
                description=description,
                category_id=category_id,
                product_type=product_type,
                unit_price=unit_price,
                cost_price=cost_price,
                unit_of_measure=unit_of_measure,
                track_inventory=track_inventory,
                image_path=image_path,
                sale_unit=sale_unit,
                min_weight=min_weight,
                max_weight=max_weight,
                weight_decimal_places=weight_decimal_places,
            )

            if product_type is ProductType.COMBO:
                repo.get_or_create_combo(product.id)

            return _to_dto(repo, product)

    def delete_product(self, product_id: int) -> None:
        with session_scope() as session:
            repo = ProductRepository(session)
            product = repo.get(product_id)
            if product is None:
                raise NotFoundError(f"No existe el producto con id={product_id}.")
            if repo.has_recipe_or_combo_references(product_id):
                raise BusinessRuleViolationError(
                    "No se puede eliminar: el producto está utilizado en una receta o combo."
                )
            repo.delete(product)

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

    # -- Códigos de barras ------------------------------------------------

    def list_barcodes(self, product_id: int) -> list[ProductBarcodeDTO]:
        with session_scope() as session:
            repo = ProductRepository(session)
            return [
                ProductBarcodeDTO(id=b.id, code=b.code) for b in repo.list_barcodes(product_id)
            ]

    def find_barcode_conflict(
        self, code: str, *, exclude_barcode_id: int | None = None
    ) -> ProductDTO | None:
        """Para el formulario de producto: ¿este código ya pertenece a otro
        producto? `exclude_barcode_id` deja pasar el propio código sin
        cambios al "modificar" uno existente. No confundir con
        `find_product_by_barcode` (Ventas): ese resuelve un escaneo real,
        este valida antes de guardar."""
        code = code.strip()
        with session_scope() as session:
            repo = ProductRepository(session)
            existing = repo.get_barcode_by_code(code)
            if existing is None or existing.id == exclude_barcode_id:
                return None
            owner = repo.get(existing.product_id)
            return _to_dto(repo, owner) if owner is not None else None

    def get_product_names(self, product_ids: list[int]) -> dict[int, str]:
        """Nombres de varios productos por id, en una sola consulta — para
        pantallas que solo necesitan mostrar el nombre (ej. el historial
        de lecturas de código de barras), sin traer el producto completo."""
        with session_scope() as session:
            return ProductRepository(session).get_names_by_ids(product_ids)

    def get_product(self, product_id: int) -> ProductDTO | None:
        """Un producto puntual por `id`, o `None` si no existe — análogo a
        `find_product_by_barcode` pero por id. Usado por consumidores que ya
        conocen el id y solo necesitan ese producto (ej.
        `GET /api/v1/products/{id}` de la API), sin traer el catálogo
        completo."""
        with session_scope() as session:
            repo = ProductRepository(session)
            product = repo.get(product_id)
            return _to_dto(repo, product) if product is not None else None

    def find_product_by_barcode(self, code: str) -> ProductDTO | None:
        """Única fuente de verdad para resolver un código de barras
        escaneado a un producto — la usa Ventas al escanear, y cualquier
        otro consumidor futuro debe llamar este método en vez de
        recalcularlo."""
        with session_scope() as session:
            repo = ProductRepository(session)
            product = repo.find_by_barcode(code.strip())
            return _to_dto(repo, product) if product is not None else None

    def generate_unique_barcode(self) -> str:
        """Genera un EAN-13 válido garantizado libre en la base de datos —
        verifica antes de devolverlo, nunca puede chocar con uno
        existente (botón "Generar código automáticamente")."""
        with session_scope() as session:
            repo = ProductRepository(session)
            for _ in range(_MAX_BARCODE_GENERATION_ATTEMPTS):
                candidate = generate_ean13_candidate()
                if repo.get_barcode_by_code(candidate) is None:
                    return candidate
        raise BusinessRuleViolationError(
            "No se pudo generar un código de barras único. Intenta de nuevo."
        )

    def add_barcode(self, product_id: int, code: str) -> ProductBarcodeDTO:
        code = code.strip()
        if not code:
            raise BusinessRuleViolationError("El código de barras no puede estar vacío.")
        if len(code) > MAX_BARCODE_LENGTH:
            raise BusinessRuleViolationError(
                f"El código de barras no puede tener más de {MAX_BARCODE_LENGTH} caracteres."
            )
        with session_scope() as session:
            repo = ProductRepository(session)
            product = repo.get(product_id)
            if product is None:
                raise NotFoundError(f"No existe el producto con id={product_id}.")
            existing = repo.get_barcode_by_code(code)
            if existing is not None:
                label = _barcode_owner_label(repo, existing.product_id)
                raise ConflictError(f"Ese código de barras ya está registrado en: {label}.")
            try:
                barcode = repo.add_barcode(product_id, code)
            except IntegrityError as error:
                # La verificación de arriba no detectó el conflicto porque
                # otra transacción concurrente insertó el mismo código justo
                # en el medio (dos estaciones sincronizadas creando el mismo
                # código casi al mismo tiempo) — la restricción UNIQUE de la
                # base de datos sí lo detiene; acá se traduce ese fallo en el
                # mismo mensaje claro, en vez de dejar pasar la excepción
                # cruda de SQLAlchemy.
                raise ConflictError(
                    "Ese código de barras acaba de ser registrado por otra operación. "
                    "Verifica el catálogo e inténtalo de nuevo."
                ) from error
            return ProductBarcodeDTO(id=barcode.id, code=barcode.code)

    def update_barcode(self, barcode_id: int, code: str) -> ProductBarcodeDTO:
        code = code.strip()
        if not code:
            raise BusinessRuleViolationError("El código de barras no puede estar vacío.")
        if len(code) > MAX_BARCODE_LENGTH:
            raise BusinessRuleViolationError(
                f"El código de barras no puede tener más de {MAX_BARCODE_LENGTH} caracteres."
            )
        with session_scope() as session:
            repo = ProductRepository(session)
            existing = repo.get_barcode_by_code(code)
            if existing is not None and existing.id != barcode_id:
                label = _barcode_owner_label(repo, existing.product_id)
                raise ConflictError(f"Ese código de barras ya está registrado en: {label}.")
            try:
                barcode = repo.update_barcode(barcode_id, code)
            except IntegrityError as error:
                raise ConflictError(
                    "Ese código de barras acaba de ser registrado por otra operación. "
                    "Verifica el catálogo e inténtalo de nuevo."
                ) from error
            if barcode is None:
                raise NotFoundError(f"No existe el código de barras con id={barcode_id}.")
            return ProductBarcodeDTO(id=barcode.id, code=barcode.code)

    def remove_barcode(self, barcode_id: int) -> None:
        with session_scope() as session:
            ProductRepository(session).remove_barcode(barcode_id)
