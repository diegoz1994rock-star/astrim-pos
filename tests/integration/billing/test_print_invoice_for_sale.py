"""Pruebas de integración de `billing/application/print_helper.py`: sin
impresora asignada a la caja (o sin usuario autenticado) cae siempre al
`ReceiptPrinter` de siempre — comportamiento actual preservado; con una
impresora asignada, el helper la resuelve y delega en
`PrinterService.print_document`.

No cubre acá el envío real de bytes/imagen por la impresora asignada
(`print_document` rasteriza el PDF con `QPdfDocument`, que exige una
`QApplication` funcional — no disponible en este sandbox, ver
`tests/integration/printers/test_printer_service.py`); esa vía se certifica
por lectura/compilación/lint. Lo que sí se verifica de punta a punta acá,
con SQLite real y sin mocks, es el enrutamiento — que nunca se pierde una
factura o un abono por falta de impresora configurada, y que un fallo de
`generate_invoice` (no relacionado con la impresora) se sigue propagando
igual que antes de este helper."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from pos.core.exceptions import DomainError
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.application.print_helper import (
    print_debt_payment_receipt,
    print_invoice_for_sale,
)
from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.printers.domain.enums import ConnectionType, PrintMethod
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures


class _SpyReceiptPrinter:
    def __init__(self) -> None:
        self.printed_paths: list[Path] = []

    def print_receipt(self, pdf_path: Path) -> None:
        self.printed_paths.append(pdf_path)


def _complete_cash_sale(sales_env: SalesFixtures) -> int:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(1))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(1000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    return sale.id


def _register_register_printer(printer_service: PrinterService, cash_register_id: int):
    return printer_service.create_device(
        name="Impresora de prueba", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.0.2.10", ip_port=9100,
        cash_register_id=cash_register_id,
    )


def test_falls_back_to_receipt_printer_without_assigned_printer(
    sales_env: SalesFixtures, billing_service: BillingService, printer_service: PrinterService,
) -> None:
    sale_id = _complete_cash_sale(sales_env)
    default_register = sales_env.cash_register_service.list_registers()[0]
    spy = _SpyReceiptPrinter()

    outcome = print_invoice_for_sale(
        billing_service=billing_service, printer_service=printer_service, receipt_printer=spy,
        sale_id=sale_id, cash_register_id=default_register.id, user_id=sales_env.user_id,
    )

    assert outcome.printed is True
    assert outcome.used_configured_printer is False
    assert len(spy.printed_paths) == 1
    assert spy.printed_paths[0].exists()


def test_falls_back_to_receipt_printer_without_cash_register_id(
    sales_env: SalesFixtures, billing_service: BillingService, printer_service: PrinterService,
) -> None:
    sale_id = _complete_cash_sale(sales_env)
    spy = _SpyReceiptPrinter()

    outcome = print_invoice_for_sale(
        billing_service=billing_service, printer_service=printer_service, receipt_printer=spy,
        sale_id=sale_id, cash_register_id=None, user_id=sales_env.user_id,
    )

    assert outcome.printed is True
    assert outcome.used_configured_printer is False
    assert len(spy.printed_paths) == 1


def test_falls_back_to_receipt_printer_when_no_user_authenticated(
    sales_env: SalesFixtures, billing_service: BillingService, printer_service: PrinterService,
) -> None:
    """Aunque haya una impresora asignada a la caja, sin usuario
    autenticado nunca se intenta una impresión anónima — cae al visor del
    sistema, igual que sin ninguna impresora configurada."""
    sale_id = _complete_cash_sale(sales_env)
    default_register = sales_env.cash_register_service.list_registers()[0]
    _register_register_printer(printer_service, default_register.id)
    spy = _SpyReceiptPrinter()

    outcome = print_invoice_for_sale(
        billing_service=billing_service, printer_service=printer_service, receipt_printer=spy,
        sale_id=sale_id, cash_register_id=default_register.id, user_id=None,
    )

    assert outcome.printed is True
    assert outcome.used_configured_printer is False
    assert len(spy.printed_paths) == 1


def test_generate_invoice_error_propagates_uncaught(
    sales_env: SalesFixtures, billing_service: BillingService, printer_service: PrinterService,
) -> None:
    """Un fallo de `generate_invoice` (ej. venta anulada) no tiene nada que
    ver con la impresora — debe seguir propagándose tal cual, como ya lo
    hacía antes de que existiera este helper."""
    sale_id = _complete_cash_sale(sales_env)
    sales_env.sales_service.void_sale(
        sale_id=sale_id, warehouse_id=sales_env.warehouse_id, reason="Prueba",
        created_by_user_id=sales_env.user_id,
    )
    spy = _SpyReceiptPrinter()

    with pytest.raises(DomainError):
        print_invoice_for_sale(
            billing_service=billing_service, printer_service=printer_service,
            receipt_printer=spy, sale_id=sale_id, cash_register_id=None,
            user_id=sales_env.user_id,
        )
    assert spy.printed_paths == []


def test_debt_receipt_falls_back_to_receipt_printer_without_assigned_printer(
    sales_env: SalesFixtures, billing_service: BillingService, printer_service: PrinterService,
) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(2))],
        payments=[
            SalePaymentInput(payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal(2000))
        ],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=sales_env.customer_id,
        created_by_user_id=sales_env.user_id,
    )
    invoice = billing_service.generate_invoice(sale.id, credit_amount=Decimal(2000))
    receipt = billing_service.register_payment(
        invoice_id=invoice.id, customer_id=sales_env.customer_id, amount=Decimal(500),
        payment_method=PaymentMethod.CASH, cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )
    assert receipt.pdf_path is not None
    spy = _SpyReceiptPrinter()

    outcome = print_debt_payment_receipt(
        printer_service=printer_service, receipt_printer=spy, pdf_path=Path(receipt.pdf_path),
        receipt_number=receipt.receipt_number, invoice_id=invoice.id, cash_register_id=None,
        user_id=sales_env.user_id,
    )

    assert outcome.printed is True
    assert outcome.used_configured_printer is False
    assert spy.printed_paths == [Path(receipt.pdf_path)]
