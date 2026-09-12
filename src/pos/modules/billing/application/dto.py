"""DTOs del módulo de Facturación."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class InvoiceDTO:
    id: int
    sale_id: int
    invoice_number: str
    issued_at: datetime
    customer_name_snapshot: str | None
    customer_document_snapshot: str | None
    tax_total: Decimal
    total: Decimal
    pdf_path: str | None
    balance_due: Decimal = Decimal(0)


@dataclass(frozen=True)
class InvoiceHistoryEntryDTO:
    """Una fila del historial de facturas de un cliente (`CustomerHistoryDialog`)."""

    invoice_id: int
    sale_id: int
    invoice_number: str
    issued_at: datetime
    original_amount: Decimal
    balance_due: Decimal
    paid_amount: Decimal
    """`original_amount - balance_due` — cuánto se ha abonado hasta ahora."""
    status: str
    """"Pendiente" o "Pagada" — derivado de `balance_due > 0`."""
    due_date: date | None
    is_overdue: bool
    """`due_date` ya pasó y todavía tiene saldo pendiente — nunca `True`
    para facturas de contado (`due_date is None`)."""
    last_payment_at: datetime | None
    cashier_name: str
    cash_register_name: str
    branch_location: str
    """`CashRegisterDTO.location` de la caja donde se hizo la venta — el
    sistema no tiene un concepto de "sucursal" propio (POS de un solo
    local con varios puntos de caja), esta es la aproximación más cercana
    disponible ya existente en el modelo de datos."""


@dataclass(frozen=True)
class DebtPaymentReceiptEntryDTO:
    """Una fila permanente del "extracto bancario" de abonos de un cliente
    (`BillingService.register_payment`/`list_customer_payment_receipts`) —
    nunca se borra."""

    receipt_number: str
    invoice_id: int
    invoice_number: str
    paid_at: datetime
    amount: Decimal
    cashier_name: str
    cash_register_name: str
    payment_method_label: str
    note: str | None
    workstation: str | None
    pdf_path: str | None = None
    """Ruta del recibo ya renderizado — permite reimprimirlo sin
    regenerarlo (ver `CustomerHistoryDialog`, doble clic en la tabla de
    abonos)."""


@dataclass(frozen=True)
class DailyPaymentEntryDTO:
    """Una fila de "Abonos recibidos hoy" (Ventas → Historial) — igual que
    `DebtPaymentReceiptEntryDTO` pero de CUALQUIER cliente en el rango
    (esa es por-cliente), con el nombre del cliente en vez del número de
    factura como dato principal."""

    customer_name: str
    invoice_number: str
    amount: Decimal
    paid_at: datetime
    cashier_name: str
    cash_register_name: str
    payment_method_label: str


@dataclass(frozen=True)
class CashierPaymentTotalDTO:
    user_id: int
    cashier_name: str
    total: Decimal


@dataclass(frozen=True)
class DailyPaymentSummaryDTO:
    """Resumen de abonos de un rango (Ventas → Historial, "Abonos
    recibidos hoy"/"Abonos por cajero") — ver `BillingService.
    get_daily_payment_summary`."""

    total: Decimal
    entries: list[DailyPaymentEntryDTO] = field(default_factory=list)
    by_cashier: list[CashierPaymentTotalDTO] = field(default_factory=list)
