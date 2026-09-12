"""Acceso a datos de categorías."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.products.infrastructure.models import Category, Product


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Category]:
        return list(
            self._session.scalars(
                select(Category).where(Category.is_deleted.is_(False)).order_by(Category.name)
            )
        )

    def get(self, category_id: int) -> Category | None:
        return self._session.get(Category, category_id)

    def get_by_name(self, name: str) -> Category | None:
        return self._session.scalar(select(Category).where(Category.name == name))

    def create(self, *, name: str) -> Category:
        category = Category(name=name, is_active=True)
        self._session.add(category)
        self._session.flush()
        return category

    def update(self, category: Category, *, name: str) -> None:
        category.name = name
        self._session.flush()

    def set_active(self, category: Category, is_active: bool) -> None:
        category.is_active = is_active

    def has_products(self, category_id: int) -> bool:
        return (
            self._session.scalar(
                select(Product.id).where(
                    Product.category_id == category_id, Product.is_deleted.is_(False)
                )
            )
            is not None
        )

    def delete(self, category: Category) -> None:
        category.is_deleted = True
        category.is_active = False
