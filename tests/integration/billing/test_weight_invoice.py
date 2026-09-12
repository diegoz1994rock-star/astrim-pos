"""La factura de una venta por peso debe mostrar el peso vendido y su
unidad (`"2.350 kg"`, no un número ambiguo) y dejar explícito que el
precio es por unidad de peso (`"$X / kg"`) — el cálculo debe coincidir
exactamente con la venta, nunca aproximado."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.infrastructure.pdf_renderer import (
    _format_item_quantity,
    _format_item_unit_price,
)
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.sales.application.dto import SaleItemDTO, SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures


def _weight_sale_item_dto(**overrides) -> SaleItemDTO:
    kwargs = {
        "id": 1,
        "product_id": 1,
        "product_name": "Carne molida",
        "quantity": Decimal("2.350"),
        "unit_price": Decimal("20000"),
        "discount_amount": Decimal("0"),
        "tax_amount": Decimal("0"),
        "line_total": Decimal("47000"),
        "sale_unit": SaleUnit.WEIGHT,
        "unit_of_measure": "kg",
    }
    kwargs.update(overrides)
    return SaleItemDTO(**kwargs)


def test_format_item_quantity_shows_weight_and_unit() -> None:
    item = _weight_sale_item_dto()
    assert _format_item_quantity(item) == "2.350 kg"


def test_format_item_quantity_for_unit_sale_shows_bare_number() -> None:
    item = _weight_sale_item_dto(
        sale_unit=SaleUnit.UNIT, unit_of_measure="unidad", quantity=Decimal("3")
    )
    assert _format_item_quantity(item) == "3"


def test_format_item_unit_price_shows_per_unit_of_weight() -> None:
    item = _weight_sale_item_dto()
    label = _format_item_unit_price(item)
    assert "/ kg" in label


def test_format_item_unit_price_for_unit_sale_has_no_suffix() -> None:
    item = _weight_sale_item_dto(sale_unit=SaleUnit.UNIT, unit_of_measure="unidad")
    label = _format_item_unit_price(item)
    assert "/" not in label


def test_generate_invoice_for_weight_sale_creates_pdf_with_matching_total(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    product_service = ProductManagementService(sales_env.event_bus)
    product = product_service.create_product(
        sku="PESO-FACT",
        name="Carne molida",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("20000"),
        cost_price=Decimal("12000"),
        unit_of_measure="kg",
        track_inventory=True,
        sale_unit=SaleUnit.WEIGHT,
    )
    sales_env.inventory_service.register_entry(
        product_id=product.id,
        warehouse_id=sales_env.warehouse_id,
        quantity=Decimal("20.000"),
        reason="Stock inicial",
        created_by_user_id=None,
    )
    weight = Decimal("2.350")
    expected_total = weight * Decimal("20000")
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=product.id, quantity=weight)],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=expected_total)],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    invoice = billing_service.generate_invoice(sale.id)

    assert invoice.pdf_path is not None
    assert invoice.total == expected_total
    reloaded_sale = sales_env.sales_service.get_sale(sale.id)
    assert reloaded_sale.items[0].sale_unit is SaleUnit.WEIGHT
    assert reloaded_sale.items[0].unit_of_measure == "kg"
    assert reloaded_sale.items[0].quantity == weight
