"""Modelos SQLAlchemy de facturación.

`Invoice.sale_id` referencia `sales.id` (módulo `sales`) sin importarlo, y
`DebtPaymentReceipt.cash_session_id` referencia `cash_sessions.id` (módulo
`cash_register`) de la misma forma, según ARCHITECTURE.md §12b.
`DebtPaymentReceipt.payment_method` reutiliza el enum de `sales` — Billing
ya depende de `sales.domain.enums` en otros puntos de este módulo.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.sales.domain.enums import PaymentMethod


class Invoice(Base):
    """Comprobante/factura emitido a partir de una venta completada.

    Guarda una copia (`customer_name_snapshot`, `customer_document_snapshot`)
    de los datos del cliente al momento de facturar, para que la factura no
    cambie retroactivamente si el cliente edita sus datos después.
    """

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), unique=True, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    customer_name_snapshot: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_document_snapshot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    balance_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    """Saldo pendiente de una venta a crédito (0 para facturas de contado y
    para facturas de crédito ya saldadas, se descuenta con cada abono — ver
    `BillingService.generate_invoice`/`register_payment`)."""
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    """Fecha límite de pago — solo se fija en facturas de crédito (`issued_at`
    + 90 días, ver `BillingService.generate_invoice`). `None` en facturas de
    contado: nunca se consideran vencidas."""


class DebtPaymentReceipt(Base):
    """Recibo permanente de un abono a una factura de crédito — nunca se
    borra, es el "extracto bancario" del cliente (`BillingService.
    register_payment`/`list_customer_payment_receipts`). Siempre aplica a
    una única factura; un abono parcial dentro del saldo de esa factura
    deja varios recibos acumulados hasta saldarla."""

    __tablename__ = "debt_payment_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False), nullable=False
    )
    cash_session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id"), nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workstation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    """Nombre del equipo donde se registró (`platform.node()`) — legible
    para auditoría, a diferencia del hash de una vía usado para licencias
    (`licensing/infrastructure/hardware.py::get_hardware_fingerprint`)."""
    paid_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Ruta del PDF ya renderizado por `BillingService._render_receipt_pdf`
    — se completa justo después de crear la fila (mismo patrón en dos pasos
    que `Invoice.pdf_path`). Permite reabrir/reimprimir el recibo desde
    `CustomerHistoryDialog` sin volver a generarlo."""
