"""Pruebas de integración del Resumen Diario de Caja: `SalesService.
get_daily_totals` ya se prueba en `tests/integration/sales/test_sale_service.py`
— este archivo cubre el lado de abonos, `BillingService.
get_daily_payment_summary`, incluyendo la decisión de diseño de que NO
filtra por `Customer.credit_history_cleared_at` (el cierre de caja del día
debe reflejar el dinero real que entró, sin importar si un cliente "borró"
su propio historial después)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pos.core.database.base import today_utc_bounds
from pos.core.database.session import session_scope
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.infrastructure.models import DebtPaymentReceipt
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.users.infrastructure.models import User
from tests.integration.sales.conftest import SalesFixtures


def _complete_credit_sale_and_pay(
    sales_env: SalesFixtures, billing_service: BillingService, *, amount: Decimal
) -> tuple[int, str]:
    """`amount` debe ser múltiplo de 1000 (precio unitario del producto de
    prueba) — la cantidad se deriva de él para que pagos y venta cuadren."""
    quantity = amount / Decimal(1000)
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=quantity)],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=amount)],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=sales_env.customer_id,
        created_by_user_id=sales_env.user_id,
    )
    invoice = billing_service.generate_invoice(sale.id, credit_amount=amount)
    receipt = billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=amount,
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )
    return invoice.id, receipt.receipt_number


def test_get_daily_payment_summary_totals_and_entries(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    invoice_id, receipt_number = _complete_credit_sale_and_pay(
        sales_env, billing_service, amount=Decimal(3000)
    )

    start, end = today_utc_bounds()
    summary = billing_service.get_daily_payment_summary(start, end)

    assert summary.total == Decimal(3000)
    assert len(summary.entries) == 1
    entry = summary.entries[0]
    assert entry.amount == Decimal(3000)
    assert entry.customer_name == "Cliente Test"
    assert entry.cashier_name == "Cajero de Ventas"
    assert entry.payment_method_label == "Efectivo"
    assert len(summary.by_cashier) == 1
    assert summary.by_cashier[0].total == Decimal(3000)
    assert summary.by_cashier[0].cashier_name == "Cajero de Ventas"
    assert invoice_id > 0
    assert receipt_number.startswith("R-")


def test_get_daily_payment_summary_excludes_receipts_outside_range(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    _complete_credit_sale_and_pay(sales_env, billing_service, amount=Decimal(1000))

    with session_scope() as session:
        receipt = session.query(DebtPaymentReceipt).one()
        receipt.paid_at = receipt.paid_at - timedelta(days=2)

    start, end = today_utc_bounds()
    summary = billing_service.get_daily_payment_summary(start, end)

    assert summary.total == Decimal(0)
    assert summary.entries == []
    assert summary.by_cashier == []


def test_get_daily_payment_summary_groups_by_multiple_cashiers(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    with session_scope() as session:
        other_user = User(
            username="otro_cajero",
            password_hash="hash-no-relevante",
            full_name="Otro Cajero",
            is_active=True,
        )
        session.add(other_user)
        session.flush()
        other_user_id = other_user.id

    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(2))],
        payments=[
            SalePaymentInput(payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal(2000))
        ],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=sales_env.customer_id,
        created_by_user_id=sales_env.user_id,
    )
    invoice = billing_service.generate_invoice(sale.id, credit_amount=Decimal(2000))
    billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(2000),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=other_user_id,
    )

    _complete_credit_sale_and_pay(sales_env, billing_service, amount=Decimal(1000))

    start, end = today_utc_bounds()
    summary = billing_service.get_daily_payment_summary(start, end)

    totals_by_user = {c.user_id: c.total for c in summary.by_cashier}
    assert totals_by_user[sales_env.user_id] == Decimal(1000)
    assert totals_by_user[other_user_id] == Decimal(2000)
    assert summary.total == Decimal(3000)


def test_get_daily_payment_summary_ignores_credit_history_cleared_at(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """El cierre de caja del día debe ver el dinero real que entró, aunque
    el cliente haya usado "Borrar historial" después (a diferencia de
    `list_customer_payment_receipts`, que sí oculta lo anterior al corte)."""
    _complete_credit_sale_and_pay(sales_env, billing_service, amount=Decimal(2000))
    sales_env.customer_service.clear_credit_history(sales_env.customer_id)

    assert billing_service.list_customer_payment_receipts(sales_env.customer_id) == []

    start, end = today_utc_bounds()
    summary = billing_service.get_daily_payment_summary(start, end)

    assert summary.total == Decimal(2000)
    assert len(summary.entries) == 1
