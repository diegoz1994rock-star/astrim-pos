"""DTOs de entrada/salida del módulo de ventas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from pos.modules.products.domain.enums import SaleUnit
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus, SaleType
from pos.modules.scales.domain.enums import WeightEntrySource


@dataclass(frozen=True)
class SaleItemInput:
    """Línea solicitada por el cajero, antes de calcular impuestos/totales."""

    product_id: int
    quantity: Decimal
    discount_amount: Decimal = Decimal(0)
    note: str | None = None
    weight_entry_source: WeightEntrySource | None = None
    """Solo se informa en líneas por peso (ver `ScaleWeightDialog`) — `None`
    en líneas por unidad."""


@dataclass(frozen=True)
class SalePaymentInput:
    payment_method: PaymentMethod
    amount: Decimal
    reference: str | None = None


@dataclass(frozen=True)
class SaleItemDTO:
    id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    note: str | None = None
    unit_cost: Decimal | None = None
    sale_unit: SaleUnit = SaleUnit.UNIT
    unit_of_measure: str = "unidad"
    weight_entry_source: WeightEntrySource | None = None


@dataclass(frozen=True)
class SalePaymentDTO:
    id: int
    payment_method: PaymentMethod
    amount: Decimal
    reference: str | None


@dataclass(frozen=True)
class SaleDTO:
    id: int
    status: SaleStatus
    sale_type: SaleType
    customer_id: int | None
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    created_at: datetime
    created_by_user_id: int | None = None
    cash_session_id: int | None = None
    customer_name: str | None = None
    customer_document: str | None = None
    items: list[SaleItemDTO] = field(default_factory=list)
    payments: list[SalePaymentDTO] = field(default_factory=list)


@dataclass(frozen=True)
class SalePreviewLineDTO:
    """Línea calculada de una venta aún no persistida (sin `id`)."""

    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    note: str | None = None
    sale_unit: SaleUnit = SaleUnit.UNIT
    unit_of_measure: str = "unidad"


@dataclass(frozen=True)
class SalePreviewDTO:
    """Totales calculados del carrito antes de confirmar la venta — no
    tiene `id`, `status` ni `created_at` porque nada se ha persistido."""

    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[SalePreviewLineDTO] = field(default_factory=list)


@dataclass(frozen=True)
class CashierSalesTotalDTO:
    """Total vendido por un cajero en un rango — `user_id` sin nombre
    resuelto (Ventas no conoce Usuarios; quien llama resuelve el nombre,
    ver `SalesHistoryViewModel`)."""

    user_id: int
    total: Decimal


@dataclass(frozen=True)
class DailySalesTotalsDTO:
    """Resumen de ventas de un rango (Ventas → Historial, "Ventas del
    día"/"Ventas por cajero") — ver `SalesService.get_daily_totals`."""

    total: Decimal
    by_cashier: list[CashierSalesTotalDTO] = field(default_factory=list)
