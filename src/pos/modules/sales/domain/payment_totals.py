"""Cálculo de "cuánto de una venta/abono fue en efectivo" — función pura de
dominio, única definición reutilizada tanto por `SalesService.complete_sale`
(para mover la caja) como por la decisión de abrir el cajón monedero
automáticamente (`SaleViewModel.open_drawer_if_applicable`) — nunca
duplicada."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from pos.modules.sales.domain.enums import PaymentMethod


class _HasCashPayment(Protocol):
    payment_method: PaymentMethod
    amount: Decimal


def cash_amount(payments: list[_HasCashPayment]) -> Decimal:
    """Suma el componente en efectivo de una lista de pagos — funciona
    tanto con `SalePaymentInput` (antes de persistir) como con
    `SalePaymentDTO`/`SalePayment` (ya persistidos), cualquier objeto con
    `payment_method`/`amount`."""
    return sum(
        (p.amount for p in payments if p.payment_method is PaymentMethod.CASH), Decimal(0)
    )
