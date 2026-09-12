"""Pruebas de `SalesHistoryViewModel` con dependencias simuladas (`Mock`):
reimprimir la factura de una venta desde el historial (genera si no existe,
la reutiliza si ya existe — `BillingService.generate_invoice` es
idempotente) — sin impresora asignada a la caja de la venta, cae al
`ReceiptPrinter` de siempre."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.sales.presentation.sales_history_view_model import SalesHistoryViewModel


def _make_view_model() -> tuple[SalesHistoryViewModel, Mock, Mock, Mock]:
    sales_service = Mock()
    sales_service.get_sale.return_value = Mock(cash_session_id=None)
    billing_service = Mock()
    receipt_printer = Mock()
    printer_service = Mock()
    printer_service.get_default_for_cash_register.return_value = None
    session_manager = Mock()
    session_manager.current = Mock(user_id=1, username="cajero")
    cash_register_service = Mock()
    view_model = SalesHistoryViewModel(
        sales_service,
        Mock(),  # inventory_service
        billing_service,
        session_manager,
        receipt_printer,
        Mock(),  # user_service
        cash_register_service,
        printer_service,
    )
    return view_model, billing_service, receipt_printer, sales_service


def test_open_invoice_pdf_generates_and_prints_without_configured_printer(qtbot: QtBot) -> None:
    view_model, billing_service, receipt_printer, _sales_service = _make_view_model()
    invoice = Mock()
    invoice.pdf_path = "/tmp/facturas/F-000001.pdf"
    billing_service.generate_invoice.return_value = invoice

    view_model.open_invoice_pdf(sale_id=42)

    billing_service.generate_invoice.assert_called_once_with(42, credit_amount=Decimal(0))
    receipt_printer.print_receipt.assert_called_once_with(Path("/tmp/facturas/F-000001.pdf"))


def test_open_invoice_pdf_reuses_existing_invoice_idempotently(qtbot: QtBot) -> None:
    """`generate_invoice` ya es idempotente en `BillingService` — este view
    model no debe intentar "arreglar" ni regenerar nada, solo pedirle la
    factura y reimprimir lo que devuelva."""
    view_model, billing_service, receipt_printer, _sales_service = _make_view_model()
    invoice = Mock()
    invoice.pdf_path = "/tmp/facturas/F-000002.pdf"
    billing_service.generate_invoice.return_value = invoice

    view_model.open_invoice_pdf(sale_id=7)
    view_model.open_invoice_pdf(sale_id=7)

    assert billing_service.generate_invoice.call_count == 2
    assert receipt_printer.print_receipt.call_count == 2


def test_open_invoice_pdf_emits_error_on_domain_error(qtbot: QtBot) -> None:
    view_model, billing_service, receipt_printer, _sales_service = _make_view_model()
    billing_service.generate_invoice.side_effect = BusinessRuleViolationError("no facturable")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.open_invoice_pdf(sale_id=1)

    assert errors == ["no facturable"]
    receipt_printer.print_receipt.assert_not_called()


def test_open_invoice_pdf_resolves_cash_register_from_sale_session(qtbot: QtBot) -> None:
    """Reimprime usando la impresora asignada a la caja donde se hizo la
    venta original (resuelta vía `cash_session_id` → `cash_register_id`),
    no la caja actualmente activa en pantalla."""
    view_model, billing_service, _receipt_printer, sales_service = _make_view_model()
    sales_service.get_sale.return_value = Mock(cash_session_id=55)
    view_model._cash_register_service.get_session.return_value = Mock(cash_register_id=9)
    view_model._printer_service.get_default_for_cash_register.return_value = None
    invoice = Mock()
    invoice.pdf_path = "/tmp/facturas/F-000003.pdf"
    billing_service.generate_invoice.return_value = invoice

    view_model.open_invoice_pdf(sale_id=42)

    view_model._cash_register_service.get_session.assert_called_once_with(55)
    view_model._printer_service.get_default_for_cash_register.assert_called_once_with(9)
