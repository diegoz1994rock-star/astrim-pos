"""Caso de uso de Facturación (PROJECT_SPEC.md, "FACTURACIÓN"): genera un
comprobante PDF a partir de una venta ya completada.

Lee `sales` (la venta) y `customers` (para el snapshot del cliente) a
través de sus servicios de aplicación — no de sus repositorios
directamente, a diferencia de otros módulos de esta pasada — porque ambos
ya exponen exactamente los datos de solo lectura que hacen falta aquí sin
necesidad de tocar su capa de infraestructura (ARCHITECTURE.md §12b permite
ambas formas; se prefiere la de menor acoplamiento cuando el servicio ya
existe).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.billing.application.dto import InvoiceDTO
from pos.modules.billing.infrastructure.models import Invoice
from pos.modules.billing.infrastructure.pdf_renderer import render_invoice_pdf
from pos.modules.billing.infrastructure.repository import BillingRepository
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.domain.enums import SaleStatus
from pos.modules.settings.application.business_settings_service import BusinessSettingsService


def _to_dto(invoice: Invoice) -> InvoiceDTO:
    return InvoiceDTO(
        id=invoice.id,
        sale_id=invoice.sale_id,
        invoice_number=invoice.invoice_number,
        issued_at=invoice.issued_at,
        customer_name_snapshot=invoice.customer_name_snapshot,
        customer_document_snapshot=invoice.customer_document_snapshot,
        tax_total=invoice.tax_total,
        total=invoice.total,
        pdf_path=invoice.pdf_path,
    )


class BillingService:
    def __init__(
        self,
        sales_service: SalesService,
        customer_service: CustomerManagementService,
        settings_service: BusinessSettingsService,
        invoices_dir: Path,
    ) -> None:
        self._sales_service = sales_service
        self._customer_service = customer_service
        self._settings_service = settings_service
        self._invoices_dir = invoices_dir

    def generate_invoice(self, sale_id: int) -> InvoiceDTO:
        sale = self._sales_service.get_sale(sale_id)
        if sale.status is not SaleStatus.COMPLETED:
            raise BusinessRuleViolationError(
                "Solo se puede facturar una venta completada (no anulada ni en borrador)."
            )

        with session_scope() as session:
            repo = BillingRepository(session)
            existing = repo.get_by_sale_id(sale_id)
            if existing is not None:
                return _to_dto(existing)

            invoice_number = f"F-{repo.count() + 1:06d}"
            customer_name = None
            customer_document = None
            if sale.customer_id is not None:
                customer = self._customer_service.get_customer(sale.customer_id)
                if customer is not None:
                    customer_name = customer.full_name
                    customer_document = customer.document_id

            issued_at = datetime.now(UTC)
            invoice = repo.create_invoice(
                sale_id=sale_id,
                invoice_number=invoice_number,
                customer_name_snapshot=customer_name,
                customer_document_snapshot=customer_document,
                tax_total=sale.tax_total,
                total=sale.total,
                pdf_path=None,
                issued_at=issued_at,
            )
            dto = _to_dto(invoice)

        business_name = self._settings_service.get_str("business_name", "Mi Negocio") or (
            "Mi Negocio"
        )
        pdf_path = self._invoices_dir / f"{invoice_number}.pdf"
        render_invoice_pdf(invoice=dto, sale=sale, business_name=business_name, file_path=pdf_path)

        with session_scope() as session:
            repo = BillingRepository(session)
            stored = repo.get(dto.id)
            assert stored is not None
            stored.pdf_path = str(pdf_path)
            return _to_dto(stored)

    def get_invoice_for_sale(self, sale_id: int) -> InvoiceDTO | None:
        with session_scope() as session:
            invoice = BillingRepository(session).get_by_sale_id(sale_id)
            return _to_dto(invoice) if invoice is not None else None

    def list_invoices(self, limit: int = 100) -> list[InvoiceDTO]:
        with session_scope() as session:
            return [_to_dto(i) for i in BillingRepository(session).list_all(limit)]
