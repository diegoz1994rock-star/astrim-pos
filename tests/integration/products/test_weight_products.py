"""Pruebas de integración de productos por peso: `min_weight`/`max_weight`/
`weight_decimal_places` solo aplican con `sale_unit is WEIGHT`, se validan
al crear/actualizar, y persisten correctamente."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType, SaleUnit


def _make_service() -> ProductManagementService:
    return ProductManagementService(EventBus())


def _create_weight_product(service: ProductManagementService, **overrides):
    kwargs = {
        "sku": "PESO-001",
        "name": "Queso Campesino",
        "description": None,
        "category_id": None,
        "product_type": ProductType.SIMPLE,
        "unit_price": Decimal("15000"),
        "cost_price": Decimal("8000"),
        "unit_of_measure": "kg",
        "track_inventory": True,
        "sale_unit": SaleUnit.WEIGHT,
    }
    kwargs.update(overrides)
    return service.create_product(**kwargs)


def test_create_weight_product_with_min_and_max(sqlite_engine: None) -> None:
    service = _make_service()

    product = _create_weight_product(
        service, min_weight=Decimal("0.100"), max_weight=Decimal("10.000")
    )

    assert product.sale_unit is SaleUnit.WEIGHT
    assert product.min_weight == Decimal("0.100")
    assert product.max_weight == Decimal("10.000")


def test_create_weight_product_without_limits_is_allowed(sqlite_engine: None) -> None:
    service = _make_service()

    product = _create_weight_product(service)

    assert product.min_weight is None
    assert product.max_weight is None


def test_weight_fields_rejected_on_unit_sale_product(sqlite_engine: None) -> None:
    service = _make_service()

    with pytest.raises(BusinessRuleViolationError):
        service.create_product(
            sku="UNIT-001",
            name="Producto por unidad",
            description=None,
            category_id=None,
            product_type=ProductType.SIMPLE,
            unit_price=Decimal("1000"),
            cost_price=Decimal("500"),
            unit_of_measure="unidad",
            track_inventory=True,
            sale_unit=SaleUnit.UNIT,
            min_weight=Decimal("0.1"),
        )


def test_max_weight_must_be_greater_than_min_weight(sqlite_engine: None) -> None:
    service = _make_service()

    with pytest.raises(BusinessRuleViolationError):
        _create_weight_product(
            service, min_weight=Decimal("5.000"), max_weight=Decimal("1.000")
        )


def test_negative_min_weight_rejected(sqlite_engine: None) -> None:
    service = _make_service()

    with pytest.raises(BusinessRuleViolationError):
        _create_weight_product(service, min_weight=Decimal("-1"))


def test_weight_decimal_places_out_of_range_rejected(sqlite_engine: None) -> None:
    service = _make_service()

    with pytest.raises(BusinessRuleViolationError):
        _create_weight_product(service, weight_decimal_places=9)


def test_update_weight_product_changes_limits(sqlite_engine: None) -> None:
    service = _make_service()
    product = _create_weight_product(service, min_weight=Decimal("0.100"))

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
        sale_unit=SaleUnit.WEIGHT,
        min_weight=Decimal("0.200"),
        max_weight=Decimal("5.000"),
    )

    assert updated.min_weight == Decimal("0.200")
    assert updated.max_weight == Decimal("5.000")


def test_weight_product_supports_fractional_quantities(sqlite_engine: None) -> None:
    """`unit_price` se sigue usando como precio por unidad de peso — un
    producto por peso no necesita ningún campo de precio adicional."""
    service = _make_service()

    product = _create_weight_product(service, min_weight=Decimal("0.001"))

    assert product.min_weight == Decimal("0.001")
