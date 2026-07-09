"""Modelo SQLAlchemy de facturación.

`sale_id` referencia `sales.id` (módulo `sales`) sin importarlo, según
ARCHITECTURE.md §12b.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, utc_now


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
    issued_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    customer_name_snapshot: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_document_snapshot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
