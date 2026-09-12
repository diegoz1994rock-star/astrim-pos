"""Pruebas de integración de ProductManagementService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import (
    BusinessRuleViolationError,
    ConflictError,
    NotFoundError,
)
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.products.domain.events import ProductCreatedEvent


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
    )


def test_create_simple_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    product = _create_simple(service)

    assert product.sku == "SKU-001"
    assert product.product_type is ProductType.SIMPLE
    assert product.is_active is True


def test_create_product_defaults_to_unit_sale(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    product = _create_simple(service)

    assert product.sale_unit is SaleUnit.UNIT


def test_create_and_update_product_persists_weight_sale_unit(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = service.create_product(
        sku="PAPA-1",
        name="Papa",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3000"),
        cost_price=Decimal("1500"),
        unit_of_measure="kg",
        track_inventory=True,
        sale_unit=SaleUnit.WEIGHT,
    )

    assert product.sale_unit is SaleUnit.WEIGHT

    updated = service.update_product(
        product.id,
        sku=product.sku,
        name=product.name,
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=product.unit_price,
        cost_price=product.cost_price,
        unit_of_measure=product.unit_of_measure,
        track_inventory=True,
        sale_unit=SaleUnit.UNIT,
    )

    assert updated.sale_unit is SaleUnit.UNIT


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
        )


def test_set_active_deactivates_product(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service)

    updated = service.set_active(product.id, False)

    assert updated.is_active is False


def test_update_product_changes_fields(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, sku="UPD-1", name="Original")

    updated = service.update_product(
        product.id,
        sku="UPD-1",
        name="Renombrado",
        description="Nueva descripción",
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("15.00"),
        cost_price=Decimal("7.00"),
        unit_of_measure="unidad",
        track_inventory=True,
    )

    assert updated.name == "Renombrado"
    assert updated.description == "Nueva descripción"
    assert updated.unit_price == Decimal("15.00")


def test_update_product_with_sku_of_another_product_raises_conflict(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    _create_simple(service, sku="TAKEN-1", name="Uno")
    product = _create_simple(service, sku="FREE-1", name="Dos")

    with pytest.raises(ConflictError):
        service.update_product(
            product.id,
            sku="TAKEN-1",
            name=product.name,
            description=None,
            category_id=None,
            product_type=ProductType.SIMPLE,
            unit_price=product.unit_price,
            cost_price=product.cost_price,
            unit_of_measure=product.unit_of_measure,
            track_inventory=product.track_inventory,
        )


def test_update_product_keeping_its_own_sku_is_allowed(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, sku="SAME-1", name="Original")

    updated = service.update_product(
        product.id,
        sku="SAME-1",
        name="Renombrado",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=product.unit_price,
        cost_price=product.cost_price,
        unit_of_measure=product.unit_of_measure,
        track_inventory=product.track_inventory,
    )

    assert updated.sku == "SAME-1"
    assert updated.name == "Renombrado"


def test_update_unknown_product_raises_not_found(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.update_product(
            9999,
            sku="NOPE-1",
            name="No existe",
            description=None,
            category_id=None,
            product_type=ProductType.SIMPLE,
            unit_price=Decimal("1"),
            cost_price=Decimal("1"),
            unit_of_measure="unidad",
            track_inventory=True,
        )


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
    )

    service.add_combo_item(
        combo_product_id=combo.id, product_id=component.id, quantity=Decimal("2")
    )

    items = service.list_combo_items(combo.id)
    assert len(items) == 1
    assert items[0].product_name == "Hamburguesa"
    assert items[0].quantity == Decimal("2")


def test_list_products_for_inventory_excludes_untracked_and_inactive(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    tracked = _create_simple(service, sku="TRACKED-1", name="Con inventario")
    untracked = service.create_product(
        sku="UNTRACKED-1",
        name="Servicio",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10"),
        cost_price=Decimal("5"),
        unit_of_measure="unidad",
        track_inventory=False,
    )
    inactive = _create_simple(service, sku="INACTIVE-1", name="Descontinuado")
    service.set_active(inactive.id, False)

    ids = {p.id for p in service.list_products_for_inventory()}

    assert tracked.id in ids
    assert untracked.id not in ids
    assert inactive.id not in ids


def test_delete_product_removes_it_from_list(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    product = _create_simple(service, sku="DEL-1")

    service.delete_product(product.id)

    products = service.list_products()
    assert all(p.id != product.id for p in products)


def test_delete_unknown_product_raises_not_found(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.delete_product(9999)


def test_delete_product_used_as_recipe_ingredient_is_forbidden(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    ingredient = _create_simple(service, sku="ING-DEL-1", name="Harina")
    compound = service.create_product(
        sku="COMP-DEL-1",
        name="Pan",
        description=None,
        category_id=None,
        product_type=ProductType.COMPOUND,
        unit_price=Decimal("3"),
        cost_price=Decimal("1"),
        unit_of_measure="unidad",
        track_inventory=True,
    )
    service.add_recipe_item(
        recipe_product_id=compound.id,
        ingredient_product_id=ingredient.id,
        quantity=Decimal("0.2"),
        unit_of_measure="kg",
    )

    with pytest.raises(BusinessRuleViolationError):
        service.delete_product(ingredient.id)


def test_delete_product_used_as_combo_component_is_forbidden(sqlite_engine: None) -> None:
    service = ProductManagementService(EventBus())
    component = _create_simple(service, sku="COMBO-COMP-DEL-1", name="Hamburguesa")
    combo = service.create_product(
        sku="COMBO-DEL-1",
        name="Combo Familiar",
        description=None,
        category_id=None,
        product_type=ProductType.COMBO,
        unit_price=Decimal("20"),
        cost_price=Decimal("10"),
        unit_of_measure="unidad",
        track_inventory=False,
    )
    service.add_combo_item(
        combo_product_id=combo.id, product_id=component.id, quantity=Decimal("2")
    )

    with pytest.raises(BusinessRuleViolationError):
        service.delete_product(component.id)
    with pytest.raises(BusinessRuleViolationError):
        service.delete_product(combo.id)
