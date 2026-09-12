"""Pruebas de dominio puro de `cash_amount`: única definición de "cuánto de
una venta/abono fue en efectivo", reutilizada tanto para mover la caja
como para decidir si el cajón monedero debe abrirse automáticamente."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.sales.application.dto import SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.sales.domain.payment_totals import cash_amount


def test_cash_only_payment_returns_full_amount() -> None:
    payments = [SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("50000"))]
    assert cash_amount(payments) == Decimal("50000")


def test_card_payment_returns_zero() -> None:
    payments = [SalePaymentInput(payment_method=PaymentMethod.CARD, amount=Decimal("50000"))]
    assert cash_amount(payments) == Decimal("0")


def test_qr_payment_returns_zero() -> None:
    payments = [SalePaymentInput(payment_method=PaymentMethod.QR, amount=Decimal("50000"))]
    assert cash_amount(payments) == Decimal("0")


def test_nequi_payment_returns_zero() -> None:
    payments = [SalePaymentInput(payment_method=PaymentMethod.NEQUI, amount=Decimal("50000"))]
    assert cash_amount(payments) == Decimal("0")


def test_bre_b_payment_returns_zero() -> None:
    payments = [SalePaymentInput(payment_method=PaymentMethod.BRE_B, amount=Decimal("50000"))]
    assert cash_amount(payments) == Decimal("0")


def test_customer_credit_payment_returns_zero() -> None:
    payments = [
        SalePaymentInput(payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal("50000"))
    ]
    assert cash_amount(payments) == Decimal("0")


def test_transfer_payment_returns_zero() -> None:
    payments = [SalePaymentInput(payment_method=PaymentMethod.TRANSFER, amount=Decimal("50000"))]
    assert cash_amount(payments) == Decimal("0")


def test_mixed_payment_with_cash_returns_only_cash_portion() -> None:
    payments = [
        SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("20000")),
        SalePaymentInput(payment_method=PaymentMethod.CARD, amount=Decimal("30000")),
    ]
    assert cash_amount(payments) == Decimal("20000")


def test_mixed_payment_without_cash_returns_zero() -> None:
    payments = [
        SalePaymentInput(payment_method=PaymentMethod.CARD, amount=Decimal("20000")),
        SalePaymentInput(payment_method=PaymentMethod.QR, amount=Decimal("30000")),
    ]
    assert cash_amount(payments) == Decimal("0")


def test_multiple_cash_payments_are_summed() -> None:
    payments = [
        SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("10000")),
        SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("15000")),
    ]
    assert cash_amount(payments) == Decimal("25000")


def test_empty_payments_returns_zero() -> None:
    assert cash_amount([]) == Decimal("0")
