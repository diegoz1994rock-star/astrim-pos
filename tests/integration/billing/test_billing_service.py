"""Pruebas de integración de BillingService contra SQLite real."""

from __future__ import annotations

from dataclasses import replace as dataclass_replace
from decimal import Decimal
from pathlib import Path

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.invoice_settings.domain.enums import PaperSize
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures


def _complete_cash_sale(
    sales_env: SalesFixtures,
    *,
    customer_id: int | None = None,
    customer_name: str | None = None,
    customer_document: str | None = None,
) -> int:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(2))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(2000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=customer_id,
        created_by_user_id=sales_env.user_id,
        customer_name=customer_name,
        customer_document=customer_document,
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


def test_generate_invoice_builds_pdf_on_narrow_ticket_with_default_margins(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """Blinda la corrección del bug de márgenes: antes de márgenes reales
    configurables, un ticket de 58mm con el margen implícito de ReportLab
    (1 pulgada por lado) dejaba ~7mm de ancho útil — casi inutilizable.
    Con el margen por defecto de 8mm, la generación debe seguir
    completándose sin `LayoutError` de ReportLab."""
    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    settings_service.update_settings(
        dataclass_replace(current, paper_size=PaperSize.TICKET_58, show_qr=True, show_barcode=True)
    )
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

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


def test_generate_invoice_without_any_customer_data_uses_sin_nombre_sin_documento(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """Requisito: la factura nunca debe quedar con nombre/documento vacíos
    — si no hay ni `Sale.customer_name` ni `Sale.customer_id`, se guarda
    literalmente "Sin nombre"/"Sin documento", nunca `None`."""
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    assert invoice.customer_name_snapshot == "Sin nombre"
    assert invoice.customer_document_snapshot == "Sin documento"


def test_generate_invoice_prefers_sale_customer_name_over_customer_id(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """El nombre libre escrito en Ventas (`Sale.customer_name`) tiene
    prioridad sobre el `Customer` formal vinculado por `customer_id`."""
    sale_id = _complete_cash_sale(
        sales_env,
        customer_id=sales_env.customer_id,
        customer_name="Mario Gómez",
        customer_document="10203040",
    )

    invoice = billing_service.generate_invoice(sale_id)

    assert invoice.customer_name_snapshot == "Mario Gómez"
    assert invoice.customer_document_snapshot == "10203040"


def test_get_invoice_for_sale_returns_none_when_not_yet_billed(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id = _complete_cash_sale(sales_env)

    assert billing_service.get_invoice_for_sale(sale_id) is None
