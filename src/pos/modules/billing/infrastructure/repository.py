"""Acceso a datos de facturas emitidas y recibos de abono."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Row, func, select, update
from sqlalchemy.orm import Session

from pos.modules.billing.infrastructure.models import DebtPaymentReceipt, Invoice
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.sales.infrastructure.models import Sale


class BillingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_sale_id(self, sale_id: int) -> Invoice | None:
        return self._session.scalar(select(Invoice).where(Invoice.sale_id == sale_id))

    def get(self, invoice_id: int) -> Invoice | None:
        return self._session.get(Invoice, invoice_id)

    def apply_payment(self, invoice_id: int, amount: Decimal) -> Decimal | None:
        """Descuenta `amount` de `balance_due` de forma atómica a nivel de
        fila (`UPDATE ... WHERE balance_due >= amount ... RETURNING`), en vez
        de leer el saldo en Python y volver a escribirlo — dos abonos
        concurrentes a la misma factura ya no pueden pisarse (lost update) ni
        dejar el saldo negativo, y el saldo resultante devuelto es siempre el
        real post-abono (nunca uno calculado en Python contra un snapshot
        viejo). Devuelve `None` si no había saldo suficiente en el momento
        del UPDATE (otro abono concurrente se adelantó); el llamador debe
        tratarlo como "saldo insuficiente", no reintentar a ciegas."""
        result = self._session.execute(
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.balance_due >= amount)
            .values(balance_due=Invoice.balance_due - amount)
            .returning(Invoice.balance_due)
        )
        row = result.first()
        return row[0] if row is not None else None

    def count(self) -> int:
        return self._session.scalar(select(func.count()).select_from(Invoice)) or 0

    def list_all(self, limit: int = 100) -> list[Invoice]:
        return list(
            self._session.scalars(select(Invoice).order_by(Invoice.issued_at.desc()).limit(limit))
        )

    def list_by_customer(self, customer_id: int, *, after: datetime | None = None) -> list[Invoice]:
        """Todas las facturas (pendientes Y pagadas) de un cliente —
        alimenta el historial de deuda (`CustomerHistoryDialog`). Se une a
        `sales` por `Invoice.sale_id` porque el cliente vive en `Sale`, no
        en `Invoice` (mismo patrón de unión directa entre infraestructuras
        ya usado por `ProfitsRepository`, ver ARCHITECTURE.md §12b). `after`
        implementa "Borrar historial" (`Customer.credit_history_cleared_at`):
        oculta facturas emitidas antes del corte sin borrar ninguna fila."""
        query = (
            select(Invoice)
            .join(Sale, Sale.id == Invoice.sale_id)
            .where(Sale.customer_id == customer_id)
        )
        if after is not None:
            query = query.where(Invoice.issued_at > after)
        return list(self._session.scalars(query.order_by(Invoice.issued_at.desc())))

    def create_invoice(
        self,
        *,
        sale_id: int,
        invoice_number: str,
        customer_name_snapshot: str | None,
        customer_document_snapshot: str | None,
        tax_total: Decimal,
        total: Decimal,
        pdf_path: str | None,
        issued_at: datetime,
        balance_due: Decimal = Decimal(0),
        due_date: date | None = None,
    ) -> Invoice:
        invoice = Invoice(
            sale_id=sale_id,
            invoice_number=invoice_number,
            issued_at=issued_at,
            customer_name_snapshot=customer_name_snapshot,
            customer_document_snapshot=customer_document_snapshot,
            tax_total=tax_total,
            total=total,
            pdf_path=pdf_path,
            balance_due=balance_due,
            due_date=due_date,
        )
        self._session.add(invoice)
        self._session.flush()
        return invoice

    def count_receipts(self) -> int:
        return self._session.scalar(select(func.count()).select_from(DebtPaymentReceipt)) or 0

    def create_receipt(
        self,
        *,
        receipt_number: str,
        invoice_id: int,
        amount: Decimal,
        payment_method: PaymentMethod,
        cash_session_id: int,
        created_by_user_id: int | None,
        note: str | None,
        workstation: str | None,
        paid_at: datetime,
    ) -> DebtPaymentReceipt:
        receipt = DebtPaymentReceipt(
            receipt_number=receipt_number,
            invoice_id=invoice_id,
            amount=amount,
            payment_method=payment_method,
            cash_session_id=cash_session_id,
            created_by_user_id=created_by_user_id,
            note=note,
            workstation=workstation,
            paid_at=paid_at,
        )
        self._session.add(receipt)
        self._session.flush()
        return receipt

    def set_receipt_pdf_path(self, receipt_id: int, pdf_path: str) -> None:
        receipt = self._session.get(DebtPaymentReceipt, receipt_id)
        assert receipt is not None
        receipt.pdf_path = pdf_path

    def list_receipts_by_customer(
        self, customer_id: int, *, after: datetime | None = None
    ) -> list[DebtPaymentReceipt]:
        """Historial de abonos de un cliente — "extracto bancario" completo,
        se une `debt_payment_receipts → invoices → sales` para llegar al
        cliente. `after` es el mismo corte de "Borrar historial" que
        `list_by_customer`."""
        query = (
            select(DebtPaymentReceipt)
            .join(Invoice, Invoice.id == DebtPaymentReceipt.invoice_id)
            .join(Sale, Sale.id == Invoice.sale_id)
            .where(Sale.customer_id == customer_id)
        )
        if after is not None:
            query = query.where(DebtPaymentReceipt.paid_at > after)
        return list(self._session.scalars(query.order_by(DebtPaymentReceipt.paid_at.desc())))

    def list_receipts_in_range(self, start: datetime, end: datetime) -> list[Row]:
        """Todos los abonos del rango, de cualquier cliente — "Abonos
        recibidos hoy" (Ventas → Historial). Se une a `invoices` en la
        misma consulta (`invoice_number`/`customer_name_snapshot` ya viven
        ahí) para no repetir una consulta por fila; a diferencia de
        `list_receipts_by_customer`, esta NO filtra por `Customer.
        credit_history_cleared_at` — el cierre de caja del día debe
        mostrar el dinero real que entró hoy, sin importar si un cliente
        "borró" su propio historial después."""
        query = (
            select(DebtPaymentReceipt, Invoice.invoice_number, Invoice.customer_name_snapshot)
            .join(Invoice, Invoice.id == DebtPaymentReceipt.invoice_id)
            .where(DebtPaymentReceipt.paid_at >= start, DebtPaymentReceipt.paid_at <= end)
            .order_by(DebtPaymentReceipt.paid_at.desc())
        )
        return self._session.execute(query).all()

    def sum_receipts_in_range(self, start: datetime, end: datetime) -> Decimal:
        return (
            self._session.scalar(
                select(func.coalesce(func.sum(DebtPaymentReceipt.amount), 0)).where(
                    DebtPaymentReceipt.paid_at >= start, DebtPaymentReceipt.paid_at <= end
                )
            )
            or Decimal(0)
        )

    def receipt_totals_by_cashier(self, start: datetime, end: datetime) -> list[Row]:
        query = (
            select(DebtPaymentReceipt.created_by_user_id, func.sum(DebtPaymentReceipt.amount))
            .where(DebtPaymentReceipt.paid_at >= start, DebtPaymentReceipt.paid_at <= end)
            .group_by(DebtPaymentReceipt.created_by_user_id)
        )
        return self._session.execute(query).all()

    def last_payment_dates(self, invoice_ids: list[int]) -> dict[int, datetime]:
        """`{invoice_id: fecha del último abono}` — agregación en SQL
        (`MAX`/`GROUP BY`), alimenta la columna "Fecha del último abono"."""
        if not invoice_ids:
            return {}
        query = (
            select(DebtPaymentReceipt.invoice_id, func.max(DebtPaymentReceipt.paid_at))
            .where(DebtPaymentReceipt.invoice_id.in_(invoice_ids))
            .group_by(DebtPaymentReceipt.invoice_id)
        )
        return dict(self._session.execute(query).all())
