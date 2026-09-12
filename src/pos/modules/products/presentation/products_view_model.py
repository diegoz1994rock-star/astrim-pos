"""View model de administración de productos."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType


class ProductsViewModel(QObject):
    products_loaded = Signal(list)
    categories_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        product_service: ProductManagementService,
        category_service: CategoryManagementService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._product_service = product_service
        self._category_service = category_service

    def load(self) -> None:
        self.categories_loaded.emit(self._category_service.list_categories())
        self._reload_products()

    def _reload_products(self) -> None:
        self.products_loaded.emit(self._product_service.list_products())

    def create_product(self, **kwargs: object) -> ProductDTO:
        """Puede lanzar `DomainError`: a diferencia del resto de los
        métodos de este view model, este y `update_product` los dejan
        propagar en vez de convertirlos en `error_occurred` — los llama
        `ProductFormDialog` de forma síncrona para poder mostrar el error
        junto al campo correspondiente sin cerrarse. Devuelve el DTO creado
        para que el diálogo pueda aplicar los códigos de barras en espera
        (no existe `product_id` hasta que la creación termina)."""
        dto = self._product_service.create_product(**kwargs)  # type: ignore[arg-type]
        self.operation_succeeded.emit("Producto creado correctamente.")
        self._reload_products()
        return dto

    def update_product(self, product_id: int, **kwargs: object) -> ProductDTO:
        """Puede lanzar `DomainError` — ver docstring de `create_product`."""
        dto = self._product_service.update_product(product_id, **kwargs)  # type: ignore[arg-type]
        self.operation_succeeded.emit("Producto actualizado correctamente.")
        self._reload_products()
        return dto

    def set_active(self, product: ProductDTO, is_active: bool) -> None:
        try:
            self._product_service.set_active(product.id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self._reload_products()

    def delete_product(self, product_id: int) -> None:
        try:
            self._product_service.delete_product(product_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Producto eliminado correctamente.")
            self._reload_products()

    def add_recipe_item(
        self, recipe_product_id: int, ingredient_product_id: int, quantity: Decimal, unit: str
    ) -> None:
        try:
            self._product_service.add_recipe_item(
                recipe_product_id=recipe_product_id,
                ingredient_product_id=ingredient_product_id,
                quantity=quantity,
                unit_of_measure=unit,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Insumo agregado a la receta.")

    def add_combo_item(self, combo_product_id: int, product_id: int, quantity: Decimal) -> None:
        try:
            self._product_service.add_combo_item(
                combo_product_id=combo_product_id, product_id=product_id, quantity=quantity
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Producto agregado al combo.")

    @property
    def product_service(self) -> ProductManagementService:
        """Acceso directo para consultas de solo lectura desde diálogos
        secundarios (ej. listar ítems de receta/combo) sin duplicar signals."""
        return self._product_service

    @staticmethod
    def product_types() -> list[ProductType]:
        return list(ProductType)
