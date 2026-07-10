"""Acceso a datos de facturas emitidas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.billing.infrastructure.models import Invoice


class BillingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_sale_id(self, sale_id: int) -> Invoice | None:
        return self._session.scalar(select(Invoice).where(Invoice.sale_id == sale_id))

    def get(self, invoice_id: int) -> Invoice | None:
        return self._session.get(Invoice, invoice_id)

    def count(self) -> int:
        return self._session.scalar(select(func.count()).select_from(Invoice)) or 0

    def list_all(self, limit: int = 100) -> list[Invoice]:
        return list(
            self._session.scalars(select(Invoice).order_by(Invoice.issued_at.desc()).limit(limit))
        )

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
        )
        self._session.add(invoice)
        self._session.flush()
        return invoice
