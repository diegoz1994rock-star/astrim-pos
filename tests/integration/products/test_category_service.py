"""Pruebas de integración de CategoryManagementService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import ConflictError, NotFoundError
from pos.modules.products.application.category_service import CategoryManagementService


def test_create_root_category(sqlite_engine: None) -> None:
    service = CategoryManagementService()

    category = service.create_category(name="Bebidas", parent_id=None)

    assert category.name == "Bebidas"
    assert category.parent_id is None
    assert category.is_active is True


def test_create_child_category_resolves_parent_name(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    parent = service.create_category(name="Bebidas", parent_id=None)

    child = service.create_category(name="Gaseosas", parent_id=parent.id)

    assert child.parent_id == parent.id
    assert child.parent_name == "Bebidas"


def test_create_category_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    service.create_category(name="Lácteos", parent_id=None)

    with pytest.raises(ConflictError):
        service.create_category(name="Lácteos", parent_id=None)


def test_create_category_with_unknown_parent_raises_not_found(sqlite_engine: None) -> None:
    service = CategoryManagementService()

    with pytest.raises(NotFoundError):
        service.create_category(name="Huérfana", parent_id=9999)


def test_set_active_toggles_category(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    category = service.create_category(name="Temporal", parent_id=None)

    updated = service.set_active(category.id, False)

    assert updated.is_active is False


def test_list_categories_includes_created(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    service.create_category(name="Panadería", parent_id=None)

    categories = service.list_categories()

    assert any(c.name == "Panadería" for c in categories)
