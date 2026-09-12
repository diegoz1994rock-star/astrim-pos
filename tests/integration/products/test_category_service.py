"""Pruebas de integración de CategoryManagementService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType


def test_create_category(sqlite_engine: None) -> None:
    service = CategoryManagementService()

    category = service.create_category(name="Bebidas")

    assert category.name == "Bebidas"
    assert category.is_active is True


def test_create_category_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    service.create_category(name="Lácteos")

    with pytest.raises(ConflictError):
        service.create_category(name="Lácteos")


def test_create_category_with_empty_name_raises_business_rule_violation(
    sqlite_engine: None,
) -> None:
    service = CategoryManagementService()

    with pytest.raises(BusinessRuleViolationError):
        service.create_category(name="   ")


def test_update_category_renames(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    category = service.create_category(name="Bebidas")

    updated = service.update_category(category.id, name="Bebidas y jugos")

    assert updated.name == "Bebidas y jugos"


def test_update_category_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    service.create_category(name="Lácteos")
    other = service.create_category(name="Panadería")

    with pytest.raises(ConflictError):
        service.update_category(other.id, name="Lácteos")


def test_update_unknown_category_raises_not_found(sqlite_engine: None) -> None:
    service = CategoryManagementService()

    with pytest.raises(NotFoundError):
        service.update_category(9999, name="Huérfana")


def test_set_active_toggles_category(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    category = service.create_category(name="Temporal")

    updated = service.set_active(category.id, False)

    assert updated.is_active is False


def test_list_categories_includes_created(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    service.create_category(name="Panadería")

    categories = service.list_categories()

    assert any(c.name == "Panadería" for c in categories)


def test_delete_category_removes_it_from_list(sqlite_engine: None) -> None:
    service = CategoryManagementService()
    category = service.create_category(name="Temporal")

    service.delete_category(category.id)

    categories = service.list_categories()
    assert all(c.id != category.id for c in categories)


def test_delete_unknown_category_raises_not_found(sqlite_engine: None) -> None:
    service = CategoryManagementService()

    with pytest.raises(NotFoundError):
        service.delete_category(9999)


def test_delete_category_with_products_raises_business_rule_violation(
    sqlite_engine: None,
) -> None:
    category_service = CategoryManagementService()
    product_service = ProductManagementService(EventBus())
    category = category_service.create_category(name="Bebidas")
    product_service.create_product(
        sku="SKU-CAT-1",
        name="Gaseosa",
        description=None,
        category_id=category.id,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("5"),
        cost_price=Decimal("2"),
        unit_of_measure="unidad",
        track_inventory=True,
    )

    with pytest.raises(BusinessRuleViolationError):
        category_service.delete_category(category.id)
