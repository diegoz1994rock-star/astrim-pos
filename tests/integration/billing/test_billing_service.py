"""Pruebas de integración de BillingService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures


def _complete_cash_sale(sales_env: SalesFixtures, *, customer_id: int | None = None) -> int:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(2))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(2000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=customer_id,
        created_by_user_id=sales_env.user_id,
    )
    return sale.id


def test_generate_invoice_creates_a_real_pdf_file(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    assert invoice.invoice_number == "F-000001"
    assert invoice.pdf_path is not None
    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_generate_invoice_is_idempotent(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id = _complete_cash_sale(sales_env)

    first = billing_service.generate_invoice(sale_id)
    second = billing_service.generate_invoice(sale_id)

    assert first.id == second.id
    assert first.invoice_number == second.invoice_number
    assert len(billing_service.list_invoices()) == 1


def test_invoice_numbers_are_sequential(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_1 = _complete_cash_sale(sales_env)
    sale_2 = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(1))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(1000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    ).id

    invoice_1 = billing_service.generate_invoice(sale_1)
    invoice_2 = billing_service.generate_invoice(sale_2)

    assert invoice_1.invoice_number == "F-000001"
    assert invoice_2.invoice_number == "F-000002"


def test_generate_invoice_rejects_a_voided_sale(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id = _complete_cash_sale(sales_env)
    sales_env.sales_service.void_sale(
        sale_id=sale_id,
        warehouse_id=sales_env.warehouse_id,
        reason="prueba",
        created_by_user_id=sales_env.user_id,
    )

    with pytest.raises(BusinessRuleViolationError):
        billing_service.generate_invoice(sale_id)


def test_generate_invoice_snapshots_customer_data(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id = _complete_cash_sale(sales_env, customer_id=sales_env.customer_id)

    invoice = billing_service.generate_invoice(sale_id)

    assert invoice.customer_name_snapshot == "Cliente Test"


def test_generate_invoice_without_customer_has_no_snapshot(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    assert invoice.customer_name_snapshot is None


def test_get_invoice_for_sale_returns_none_when_not_yet_billed(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id = _complete_cash_sale(sales_env)

    assert billing_service.get_invoice_for_sale(sale_id) is None
