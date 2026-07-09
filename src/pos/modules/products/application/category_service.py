"""Casos de uso de administración de categorías (jerárquicas)."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.products.application.dto import CategoryDTO
from pos.modules.products.infrastructure.category_repository import CategoryRepository
from pos.modules.products.infrastructure.models import Category


def _to_dto(category: Category, parent_name: str | None) -> CategoryDTO:
    return CategoryDTO(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        parent_name=parent_name,
        is_active=category.is_active,
    )


class CategoryManagementService:
    """CRUD de categorías, con jerarquía opcional vía `parent_id`."""

    def list_categories(self) -> list[CategoryDTO]:
        with session_scope() as session:
            repo = CategoryRepository(session)
            return [
                _to_dto(category, parent_name)
                for category, parent_name in repo.list_with_parent_name()
            ]

    def create_category(self, *, name: str, parent_id: int | None) -> CategoryDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la categoría no puede estar vacío.")

        with session_scope() as session:
            repo = CategoryRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe una categoría llamada '{name}'.")
            if parent_id is not None and repo.get(parent_id) is None:
                raise NotFoundError(f"No existe la categoría padre con id={parent_id}.")

            category = repo.create(name=name, parent_id=parent_id)
            parent_name = repo.get(parent_id).name if parent_id is not None else None  # type: ignore[union-attr]
            return _to_dto(category, parent_name)

    def set_active(self, category_id: int, is_active: bool) -> CategoryDTO:
        with session_scope() as session:
            repo = CategoryRepository(session)
            category = repo.get(category_id)
            if category is None:
                raise NotFoundError(f"No existe la categoría con id={category_id}.")
            repo.set_active(category, is_active)
            parent_name = (
                repo.get(category.parent_id).name if category.parent_id is not None else None  # type: ignore[union-attr]
            )
            return _to_dto(category, parent_name)
