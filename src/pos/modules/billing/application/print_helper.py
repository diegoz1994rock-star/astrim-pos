"""Punto único para "imprimir un comprobante ya generado" — consolida los 3
sitios que antes llamaban `ReceiptPrinter.print_receipt` por separado
(`sale_view_model.py`, `sales_history_view_model.py`,
`customer_history_dialog.py`).

Resuelve la impresora asignada a la caja (`PrinterService.
get_default_for_cash_register`) e imprime con ella; si no hay ninguna
impresora configurada para esa caja (o no hay usuario autenticado, que
`PrinterService.print_document` exige), cae al comportamiento de siempre
—`ReceiptPrinter.print_receipt`, abrir el PDF con el visor del sistema
operativo— para que un negocio que no configuró nada en "Administración →
Dispositivos → Impresoras" siga funcionando exactamente igual que antes.

Un fallo de impresión NUNCA se propaga como excepción: la factura y el PDF
ya quedaron guardados por `BillingService.generate_invoice` antes de llegar
acá, así que un error de impresora solo se reporta en el `PrintOutcome`
devuelto — la venta o el abono ya completados no se pierden ni se
reintentan automáticamente."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from pos.core.exceptions import BusinessRuleViolationError, DomainError
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.application.receipt_printer import ReceiptPrinter
from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.printers.domain.enums import PrintDocumentType


@dataclass(frozen=True)
class PrintOutcome:
    printed: bool
    """`True` si el documento se envió a alguna impresora (asignada o, en su
    defecto, el visor del sistema) sin error. `False` solo cuando la
    impresora asignada devolvió un error real — nunca por falta de
    configuración."""
    used_configured_printer: bool
    printer_id: int | None
    printer_name: str | None
    open_drawer_after_print: bool
    """Copiado de `Printer.open_drawer_after_print` cuando se usó una
    impresora asignada — el llamador decide si actuar sobre esto (ver
    `SaleViewModel.open_drawer_if_applicable`, único punto real de apertura
    automática del cajón)."""
    error: str | None


def print_invoice_for_sale(
    *,
    billing_service: BillingService,
    printer_service: PrinterService,
    receipt_printer: ReceiptPrinter,
    sale_id: int,
    cash_register_id: int | None,
    user_id: int | None,
    username: str | None = None,
    credit_amount: Decimal = Decimal(0),
) -> PrintOutcome:
    """Genera la factura (idempotente — nunca regenera número ni PDF si ya
    existía) y la imprime. Deja pasar `DomainError` de `generate_invoice`
    sin capturar: es un fallo distinto y anterior a la impresión, los 3
    llamadores ya lo manejaban antes de este helper y lo siguen manejando
    igual."""
    invoice = billing_service.generate_invoice(sale_id, credit_amount=credit_amount)
    if invoice.pdf_path is None:
        return PrintOutcome(
            printed=False, used_configured_printer=False, printer_id=None, printer_name=None,
            open_drawer_after_print=False, error="No se pudo generar el comprobante.",
        )
    return _print_pdf(
        printer_service=printer_service,
        receipt_printer=receipt_printer,
        pdf_path=Path(invoice.pdf_path),
        cash_register_id=cash_register_id,
        user_id=user_id,
        username=username,
        document_type=PrintDocumentType.INVOICE,
        document_reference=invoice.invoice_number,
        sale_id=sale_id,
        invoice_id=invoice.id,
    )


def print_debt_payment_receipt(
    *,
    printer_service: PrinterService,
    receipt_printer: ReceiptPrinter,
    pdf_path: Path,
    receipt_number: str,
    invoice_id: int | None,
    cash_register_id: int | None,
    user_id: int | None,
    username: str | None = None,
) -> PrintOutcome:
    """Reimpresión (o impresión original) de un recibo de abono ya
    renderizado por `BillingService._render_receipt_pdf` — nunca modifica el
    abono ni regenera el PDF, solo lo envía a la impresora asignada."""
    return _print_pdf(
        printer_service=printer_service,
        receipt_printer=receipt_printer,
        pdf_path=pdf_path,
        cash_register_id=cash_register_id,
        user_id=user_id,
        username=username,
        document_type=PrintDocumentType.DEBT_RECEIPT,
        document_reference=receipt_number,
        sale_id=None,
        invoice_id=invoice_id,
    )


def _print_pdf(
    *,
    printer_service: PrinterService,
    receipt_printer: ReceiptPrinter,
    pdf_path: Path,
    cash_register_id: int | None,
    user_id: int | None,
    username: str | None,
    document_type: PrintDocumentType,
    document_reference: str | None,
    sale_id: int | None,
    invoice_id: int | None,
) -> PrintOutcome:
    printer = None
    if cash_register_id is not None:
        try:
            printer = printer_service.get_default_for_cash_register(cash_register_id)
        except DomainError:
            printer = None
    if printer is None or user_id is None:
        receipt_printer.print_receipt(pdf_path)
        return PrintOutcome(
            printed=True, used_configured_printer=False, printer_id=None, printer_name=None,
            open_drawer_after_print=False, error=None,
        )

    try:
        printer_service.print_document(
            printer.id,
            pdf_path,
            user_id=user_id,
            username=username,
            document_type=document_type,
            document_reference=document_reference,
            sale_id=sale_id,
            invoice_id=invoice_id,
            cash_register_id=cash_register_id,
        )
    except BusinessRuleViolationError as error:
        return PrintOutcome(
            printed=False, used_configured_printer=True, printer_id=printer.id,
            printer_name=printer.name, open_drawer_after_print=False, error=str(error),
        )
    return PrintOutcome(
        printed=True, used_configured_printer=True, printer_id=printer.id,
        printer_name=printer.name, open_drawer_after_print=printer.open_drawer_after_print,
        error=None,
    )
