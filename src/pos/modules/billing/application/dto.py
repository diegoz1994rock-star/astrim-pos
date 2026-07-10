"""DTOs del módulo de Facturación."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
