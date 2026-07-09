"""Acceso a datos de categorías."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from pos.modules.products.infrastructure.models import Category


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_with_parent_name(self) -> list[tuple[Category, str | None]]:
        parent = aliased(Category)
        rows = self._session.execute(
            select(Category, parent.name)
            .outerjoin(parent, parent.id == Category.parent_id)
            .order_by(Category.name)
        )
        return [(row[0], row[1]) for row in rows]

    def get(self, category_id: int) -> Category | None:
        return self._session.get(Category, category_id)

    def get_by_name(self, name: str) -> Category | None:
        return self._session.scalar(select(Category).where(Category.name == name))

    def create(self, *, name: str, parent_id: int | None) -> Category:
        category = Category(name=name, parent_id=parent_id, is_active=True)
        self._session.add(category)
        self._session.flush()
        return category

    def set_active(self, category: Category, is_active: bool) -> None:
        category.is_active = is_active
