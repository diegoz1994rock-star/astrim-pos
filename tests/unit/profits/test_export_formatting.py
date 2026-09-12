"""Pruebas del formateador de cantidades de Ganancias: `SaleUnit` decide el
formato, nunca un único formateador para todo — replica el bug reportado
("61.000" en vez de "61") y confirma que no vuelve a aparecer."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.products.domain.enums import SaleUnit
from pos.modules.profits.application.export_formatting import format_quantity


def test_unit_sold_quantity_is_always_a_whole_integer() -> None:
    """`sale_items.quantity` es `Numeric(14, 3)`: un `SUM` de 61 unidades
    llega como `Decimal('61.000')`, nunca debe mostrarse con decimales ni
    con formato monetario para productos vendidos por unidad."""
    assert format_quantity(Decimal("61.000"), SaleUnit.UNIT) == "61"
    assert format_quantity(Decimal("46.000"), SaleUnit.UNIT) == "46"
    assert format_quantity(Decimal("1.000"), SaleUnit.UNIT) == "1"


def test_weight_sold_quantity_keeps_only_existing_decimals() -> None:
    assert format_quantity(Decimal("2.500"), SaleUnit.WEIGHT) == "2.5"
    assert format_quantity(Decimal("1.250"), SaleUnit.WEIGHT) == "1.25"
    assert format_quantity(Decimal("0.750"), SaleUnit.WEIGHT) == "0.75"
    assert format_quantity(Decimal("15.750"), SaleUnit.WEIGHT) == "15.75"


def test_weight_sold_whole_quantity_has_no_trailing_zeros() -> None:
    assert format_quantity(Decimal("100.000"), SaleUnit.WEIGHT) == "100"
    assert format_quantity(Decimal("0.000"), SaleUnit.WEIGHT) == "0"


def test_mixed_unit_aggregate_falls_back_to_trimmed_decimal() -> None:
    """`sale_unit=None` es el caso de un agregado que mezcla productos por
    unidad y por peso (ej. total por categoría): no se puede forzar
    entero, pero tampoco debe arrastrar ceros del `Numeric` de la
    columna."""
    assert format_quantity(Decimal("61.000"), None) == "61"
    assert format_quantity(Decimal("2.500"), None) == "2.5"
