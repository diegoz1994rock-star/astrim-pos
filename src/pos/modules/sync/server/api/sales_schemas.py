"""Modelos Pydantic de la API del proceso de venta (Fases 3 y 4) — traducen
los DTOs ya definidos en `modules.sales.application.dto` (los mismos que
usa el carrito y el cobro del escritorio) a la forma JSON pública.

Fase 3 (`SalePreviewDTO`/`SalePreviewLineDTO`): sin `id`/`status`/
`created_at` porque nada está persistido todavía — ver `sales_draft_store.py`.

Fase 4 (`SaleDTO`/`SaleItemDTO`/`SalePaymentDTO`): la venta ya persistida
tras `SalesService.complete_sale`. `SaleItemSchema` omite a propósito
`SaleItemDTO.unit_cost` — dato de margen, mismo criterio que ya excluye
`cost_price` en `products_schemas.py` (Fase 2): ni la pantalla de Ventas
del escritorio se lo muestra al cajero."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from pos.modules.sales.application.dto import (
    SaleDTO,
    SaleItemDTO,
    SalePaymentDTO,
    SalePreviewDTO,
    SalePreviewLineDTO,
)
from pos.modules.sales.domain.enums import PaymentMethod


class AddSaleItemRequest(BaseModel):
    product_id: int
    quantity: Decimal
    note: str | None = None


class UpdateSaleItemRequest(BaseModel):
    quantity: Decimal
    note: str | None = None


class SaleDraftLineSchema(BaseModel):
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    note: str | None = None

    @classmethod
    def from_dto(cls, dto: SalePreviewLineDTO) -> SaleDraftLineSchema:
        return cls(
            product_id=dto.product_id,
            product_name=dto.product_name,
            quantity=dto.quantity,
            unit_price=dto.unit_price,
            discount_amount=dto.discount_amount,
            tax_amount=dto.tax_amount,
            line_total=dto.line_total,
            note=dto.note,
        )


class SaleDraftSchema(BaseModel):
    """Resumen actualizado de una venta en curso: id del carrito + los
    mismos totales que `SalePreviewDTO` ya calcula (subtotal, descuentos,
    impuestos, total) — recalculados en el momento con
    `SalesService.preview_sale`, nunca guardados aparte, para que nunca
    puedan quedar desincronizados de las líneas reales del carrito."""

    draft_id: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[SaleDraftLineSchema]

    @classmethod
    def from_preview(cls, draft_id: str, preview: SalePreviewDTO) -> SaleDraftSchema:
        return cls(
            draft_id=draft_id,
            subtotal=preview.subtotal,
            discount_total=preview.discount_total,
            tax_total=preview.tax_total,
            total=preview.total,
            items=[SaleDraftLineSchema.from_dto(line) for line in preview.items],
        )


# -- Fase 4: finalización -----------------------------------------------------


class SalePaymentRequest(BaseModel):
    payment_method: PaymentMethod
    amount: Decimal
    reference: str | None = None


class CompleteSaleRequest(BaseModel):
    payments: list[SalePaymentRequest]
    customer_id: int | None = None
    customer_name: str | None = None
    customer_document: str | None = None


class SaleItemSchema(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    note: str | None
    sale_unit: str
    unit_of_measure: str

    @classmethod
    def from_dto(cls, dto: SaleItemDTO) -> SaleItemSchema:
        return cls(
            id=dto.id,
            product_id=dto.product_id,
            product_name=dto.product_name,
            quantity=dto.quantity,
            unit_price=dto.unit_price,
            discount_amount=dto.discount_amount,
            tax_amount=dto.tax_amount,
            line_total=dto.line_total,
            note=dto.note,
            sale_unit=dto.sale_unit.value,
            unit_of_measure=dto.unit_of_measure,
        )


class SalePaymentSchema(BaseModel):
    id: int
    payment_method: str
    amount: Decimal
    reference: str | None

    @classmethod
    def from_dto(cls, dto: SalePaymentDTO) -> SalePaymentSchema:
        return cls(
            id=dto.id,
            payment_method=dto.payment_method.value,
            amount=dto.amount,
            reference=dto.reference,
        )


class CompletedSaleSchema(BaseModel):
    """La venta ya persistida — misma forma que ve el escritorio al
    completar el cobro (`SaleDTO`), devuelta tanto por
    `POST /sales/drafts/{id}/complete` como por `GET /sales/{sale_id}`."""

    id: int
    status: str
    sale_type: str
    customer_id: int | None
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    created_at: datetime
    created_by_user_id: int | None
    cash_session_id: int | None
    customer_name: str | None
    customer_document: str | None
    items: list[SaleItemSchema]
    payments: list[SalePaymentSchema]

    @classmethod
    def from_dto(cls, dto: SaleDTO) -> CompletedSaleSchema:
        return cls(
            id=dto.id,
            status=dto.status.value,
            sale_type=dto.sale_type.value,
            customer_id=dto.customer_id,
            subtotal=dto.subtotal,
            discount_total=dto.discount_total,
            tax_total=dto.tax_total,
            total=dto.total,
            created_at=dto.created_at,
            created_by_user_id=dto.created_by_user_id,
            cash_session_id=dto.cash_session_id,
            customer_name=dto.customer_name,
            customer_document=dto.customer_document,
            items=[SaleItemSchema.from_dto(item) for item in dto.items],
            payments=[SalePaymentSchema.from_dto(payment) for payment in dto.payments],
        )
