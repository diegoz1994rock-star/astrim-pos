"""Prueba unitaria de `_matches_search` (sin DB, sin Qt) — mismo criterio
que la búsqueda en vivo del escritorio (ver
`shared_ui/widgets/search_filter_proxy_model.py`): subcadena, sin
distinguir mayúsculas/minúsculas, sobre SKU + códigos de barras + nombre +
categoría."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.sync.server.api.products_router import _matches_search


def _product(
    *,
    sku: str = "SKU-1",
    name: str = "Coca-Cola 400ml",
    category_name: str | None = "Bebidas",
    barcodes: tuple[str, ...] = ("7701234567890",),
) -> ProductDTO:
    return ProductDTO(
        id=1,
        sku=sku,
        name=name,
        description=None,
        category_id=1 if category_name else None,
        category_name=category_name,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("3500"),
        cost_price=Decimal("2000"),
        unit_of_measure="unidad",
        is_active=True,
        track_inventory=True,
        sale_unit=SaleUnit.UNIT,
        barcodes=barcodes,
    )


def test_matches_by_name_substring() -> None:
    assert _matches_search(_product(name="Coca-Cola 400ml"), "coca")


def test_matches_is_case_insensitive() -> None:
    assert _matches_search(_product(name="Coca-Cola 400ml"), "COCA")


def test_matches_by_sku() -> None:
    assert _matches_search(_product(sku="ABC-123"), "abc-123")


def test_matches_by_barcode() -> None:
    assert _matches_search(_product(barcodes=("7701234567890",)), "7701234567890")


def test_matches_by_category_name() -> None:
    assert _matches_search(_product(category_name="Bebidas"), "bebidas")


def test_does_not_match_unrelated_text() -> None:
    assert not _matches_search(_product(name="Coca-Cola 400ml"), "papa")


def test_matches_with_no_category() -> None:
    """No debe reventar por `category_name=None` (producto sin categoría)."""
    assert _matches_search(_product(name="Papa", category_name=None), "papa")
