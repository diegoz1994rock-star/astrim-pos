"""Casos de uso de administración de categorías."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.products.application.dto import CategoryDTO
from pos.modules.products.infrastructure.category_repository import CategoryRepository
from pos.modules.products.infrastructure.models import Category


def _to_dto(category: Category) -> CategoryDTO:
    return CategoryDTO(id=category.id, name=category.name, is_active=category.is_active)


class CategoryManagementService:
    """CRUD de categorías."""

    def list_categories(self) -> list[CategoryDTO]:
        with session_scope() as session:
            repo = CategoryRepository(session)
            return [_to_dto(category) for category in repo.list_all()]

    def create_category(self, *, name: str) -> CategoryDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la categoría no puede estar vacío.")

        with session_scope() as session:
            repo = CategoryRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe una categoría llamada '{name}'.")
            category = repo.create(name=name)
            return _to_dto(category)

    def update_category(self, category_id: int, *, name: str) -> CategoryDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la categoría no puede estar vacío.")

        with session_scope() as session:
            repo = CategoryRepository(session)
            category = repo.get(category_id)
            if category is None:
                raise NotFoundError(f"No existe la categoría con id={category_id}.")
            existing = repo.get_by_name(name)
            if existing is not None and existing.id != category_id:
                raise ConflictError(f"Ya existe una categoría llamada '{name}'.")
            repo.update(category, name=name)
            return _to_dto(category)

    def set_active(self, category_id: int, is_active: bool) -> CategoryDTO:
        with session_scope() as session:
            repo = CategoryRepository(session)
            category = repo.get(category_id)
            if category is None:
                raise NotFoundError(f"No existe la categoría con id={category_id}.")
            repo.set_active(category, is_active)
            return _to_dto(category)

    def delete_category(self, category_id: int) -> None:
        with session_scope() as session:
            repo = CategoryRepository(session)
            category = repo.get(category_id)
            if category is None:
                raise NotFoundError(f"No existe la categoría con id={category_id}.")
            if repo.has_products(category_id):
                raise BusinessRuleViolationError(
                    "No se puede eliminar: hay productos asociados a esta categoría."
                )
            repo.delete(category)
