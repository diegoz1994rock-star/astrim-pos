"""Pruebas de integración de ProductManagementService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.domain.events import ProductCreatedEvent
from pos.modules.products.infrastructure.models import Tax


def _create_simple(
    service: ProductManagementService, sku: str = "SKU-001", name: str = "Producto Uno"
):
    return service.create_product(
        sku=sku,
        name=name,
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10.00"),
        cost_price=Decimal("5.00"),
        unit_of_measure="unidad",
        track_inventory=True,
        tax_codes=set(),
    )


def test_create_simple_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    product = _create_simple(service)

    assert product.sku == "SKU-001"
    assert product.product_type is ProductType.SIMPLE
    assert product.is_active is True


def test_create_product_publishes_created_event(sqlite_engine: None) -> None:
    bus = EventBus()
    received: list[ProductCreatedEvent] = []
    bus.subscribe(ProductCreatedEvent, received.append)
    service = ProductManagementService(bus)

    product = _create_simple(service)

    assert len(received) == 1
    assert received[0].product_id == product.id
    assert received[0].track_inventory is True


def test_create_product_with_duplicate_sku_raises_conflict(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    _create_simple(service, sku="DUP-1")

    with pytest.raises(ConflictError):
        _create_simple(service, sku="DUP-1", name="Otro nombre")


def test_create_product_with_negative_price_is_rejected(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.create_product(
            sku="NEG-1",
            name="Precio negativo",
            description=None,
            category_id=None,
            product_type=ProductType.SIMPLE,
            unit_price=Decimal("-1"),
            cost_price=Decimal("0"),
            unit_of_measure="unidad",
            track_inventory=True,
            tax_codes=set(),
        )


def test_create_product_assigns_taxes(sqlite_engine: None) -> None:
    with session_scope() as session:
        session.add(Tax(name="IVA", rate_percent=Decimal("19")))

    service = ProductManagementService(EventBus())
    product = service.create_product(
        sku="TAX-1",
        name="Con impuesto",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10"),
        cost_price=Decimal("5"),
        unit_of_measure="unidad",
        track_inventory=True,
        tax_codes={"IVA"},
    )

    assert product.tax_codes == frozenset({"IVA"})


def test_set_active_deactivates_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service)

    updated = service.set_active(product.id, False)

    assert updated.is_active is False


def test_add_recipe_item_to_compound_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    ingredient = _create_simple(service, sku="ING-1", name="Harina")
    compound = service.create_product(
        sku="COMP-1",
        name="Pan",
        description=None,
        category_id=None,
        product_type=ProductType.COMPOUND,
        unit_price=Decimal("3"),
        cost_price=Decimal("1"),
        unit_of_measure="unidad",
        track_inventory=True,
        tax_codes=set(),
    )

    service.add_recipe_item(
        recipe_product_id=compound.id,
        ingredient_product_id=ingredient.id,
        quantity=Decimal("0.2"),
        unit_of_measure="kg",
    )

    items = service.list_recipe_items(compound.id)
    assert len(items) == 1
    assert items[0].ingredient_name == "Harina"
    assert items[0].quantity == Decimal("0.2")


def test_add_recipe_item_to_simple_product_is_forbidden(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    simple = _create_simple(service, sku="SIMPLE-1")
    ingredient = _create_simple(service, sku="ING-2", name="Azúcar")

    with pytest.raises(BusinessRuleViolationError):
        service.add_recipe_item(
            recipe_product_id=simple.id,
            ingredient_product_id=ingredient.id,
            quantity=Decimal("1"),
            unit_of_measure="kg",
        )


def test_add_combo_item_to_combo_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    component = _create_simple(service, sku="COMBO-COMP-1", name="Hamburguesa")
    combo = service.create_product(
        sku="COMBO-1",
        name="Combo Familiar",
        description=None,
        category_id=None,
        product_type=ProductType.COMBO,
        unit_price=Decimal("20"),
        cost_price=Decimal("10"),
        unit_of_measure="unidad",
        track_inventory=False,
        tax_codes=set(),
    )

    service.add_combo_item(
        combo_product_id=combo.id, product_id=component.id, quantity=Decimal("2")
    )

    items = service.list_combo_items(combo.id)
    assert len(items) == 1
    assert items[0].product_name == "Hamburguesa"
    assert items[0].quantity == Decimal("2")
