"""Pruebas de integración de Cuentas por Cobrar: `BillingService.
generate_invoice(credit_amount=...)` (saldo pendiente + vencimiento),
`register_payment` (abono parcial y compuesto a una factura, numeración de
recibos, integración con el ledger de crédito y con caja),
`list_customer_debt_history`/`list_customer_payment_receipts`, y
`clear_credit_history` (oculta sin borrar nada real)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.infrastructure.models import Invoice
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures


def _complete_credit_sale(
    sales_env: SalesFixtures, *, quantity: Decimal, amount: Decimal
) -> tuple[int, Decimal]:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=quantity)],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=amount)],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=sales_env.customer_id,
        created_by_user_id=sales_env.user_id,
    )
    return sale.id, amount


def test_generate_invoice_with_credit_amount_sets_balance_due_and_due_date(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))

    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    assert invoice.balance_due == amount
    with session_scope() as session:
        stored = session.get(Invoice, invoice.id)
        assert stored is not None
        assert stored.due_date == stored.issued_at.date() + timedelta(days=90)


def test_generate_invoice_without_credit_amount_has_no_due_date(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(1))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(1000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    invoice = billing_service.generate_invoice(sale.id)

    assert invoice.balance_due == Decimal(0)
    with session_scope() as session:
        stored = session.get(Invoice, invoice.id)
        assert stored is not None
        assert stored.due_date is None


def test_credit_sale_exceeding_limit_persists_nothing(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """Cupo del cliente de prueba es 50000 (ver `sales/conftest.py`)."""
    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(100))],
            payments=[
                SalePaymentInput(
                    payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal(100000)
                )
            ],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            customer_id=sales_env.customer_id,
            created_by_user_id=sales_env.user_id,
        )

    assert sales_env.sales_service.list_recent_sales() == []


def test_register_payment_partial_then_full_settles_invoice(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(2), amount=Decimal(2000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    first_receipt = billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(800),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )
    assert first_receipt.receipt_number == "R-000001"

    history = billing_service.list_customer_debt_history(sales_env.customer_id)
    assert history[0].balance_due == Decimal(1200)
    assert history[0].paid_amount == Decimal(800)
    assert history[0].status == "Pendiente"

    second_receipt = billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(1200),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )
    assert second_receipt.receipt_number == "R-000002"

    history = billing_service.list_customer_debt_history(sales_env.customer_id)
    assert history[0].balance_due == Decimal(0)
    assert history[0].status == "Pagada"

    customer = sales_env.customer_service.get_customer(sales_env.customer_id)
    assert customer is not None
    assert customer.current_debt == Decimal(0)


def test_register_payment_rejects_amount_greater_than_balance(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    with pytest.raises(BusinessRuleViolationError):
        billing_service.register_payment(
            invoice_id=invoice.id,
            customer_id=sales_env.customer_id,
            amount=Decimal(1500),
            payment_method=PaymentMethod.CASH,
            cash_session_id=sales_env.cash_session_id,
            created_by_user_id=sales_env.user_id,
        )


def test_register_payment_rejects_already_paid_invoice(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """Regla 15 del pedido original: "Una factura pagada no puede volver a cobrarse"."""
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)
    billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(1000),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )

    with pytest.raises(BusinessRuleViolationError):
        billing_service.register_payment(
            invoice_id=invoice.id,
            customer_id=sales_env.customer_id,
            amount=Decimal(500),
            payment_method=PaymentMethod.CASH,
            cash_session_id=sales_env.cash_session_id,
            created_by_user_id=sales_env.user_id,
        )


def test_register_payment_rejects_customer_credit_as_method(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    with pytest.raises(BusinessRuleViolationError):
        billing_service.register_payment(
            invoice_id=invoice.id,
            customer_id=sales_env.customer_id,
            amount=Decimal(1000),
            payment_method=PaymentMethod.CUSTOMER_CREDIT,
            cash_session_id=sales_env.cash_session_id,
            created_by_user_id=sales_env.user_id,
        )


def test_register_payment_rejects_invoice_from_another_customer(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    other_customer = sales_env.customer_service.create_customer(
        full_name="Otro Cliente", credit_limit=Decimal("50000")
    )
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    with pytest.raises(BusinessRuleViolationError):
        billing_service.register_payment(
            invoice_id=invoice.id,
            customer_id=other_customer.id,
            amount=Decimal(1000),
            payment_method=PaymentMethod.CASH,
            cash_session_id=sales_env.cash_session_id,
            created_by_user_id=sales_env.user_id,
        )


def test_register_payment_rejects_nonexistent_invoice(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    with pytest.raises(NotFoundError):
        billing_service.register_payment(
            invoice_id=999999,
            customer_id=sales_env.customer_id,
            amount=Decimal(100),
            payment_method=PaymentMethod.CASH,
            cash_session_id=sales_env.cash_session_id,
            created_by_user_id=sales_env.user_id,
        )


def test_register_payment_registers_cash_movement_only_for_cash(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(1000),
        payment_method=PaymentMethod.CARD,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )

    movements = sales_env.cash_register_service.list_movements(sales_env.cash_session_id)
    assert not any(m.amount == Decimal(1000) for m in movements)


def test_list_customer_payment_receipts_is_permanent_audit_trail(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(1000),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        note="Pago en mostrador",
        created_by_user_id=sales_env.user_id,
    )

    receipts = billing_service.list_customer_payment_receipts(sales_env.customer_id)
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.receipt_number == "R-000001"
    assert receipt.invoice_number == invoice.invoice_number
    assert receipt.amount == Decimal(1000)
    assert receipt.cashier_name == "Cajero de Ventas"
    assert receipt.payment_method_label == "Efectivo"
    assert receipt.note == "Pago en mostrador"
    assert receipt.workstation


def test_is_overdue_true_after_due_date_passed(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)

    with session_scope() as session:
        stored = session.get(Invoice, invoice.id)
        assert stored is not None
        stored.due_date = date.today() - timedelta(days=1)

    history = billing_service.list_customer_debt_history(sales_env.customer_id)
    assert history[0].is_overdue is True


def test_is_overdue_false_once_paid(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)
    with session_scope() as session:
        stored = session.get(Invoice, invoice.id)
        assert stored is not None
        stored.due_date = date.today() - timedelta(days=1)

    billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(1000),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )

    history = billing_service.list_customer_debt_history(sales_env.customer_id)
    assert history[0].is_overdue is False


def test_clear_credit_history_hides_without_deleting_real_data(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    sale_id, amount = _complete_credit_sale(sales_env, quantity=Decimal(1), amount=Decimal(1000))
    invoice = billing_service.generate_invoice(sale_id, credit_amount=amount)
    billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(1000),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )

    sales_env.customer_service.clear_credit_history(sales_env.customer_id)

    assert billing_service.list_customer_debt_history(sales_env.customer_id) == []
    assert billing_service.list_customer_payment_receipts(sales_env.customer_id) == []

    # nada real se borró: la venta, la factura y el recibo siguen existiendo
    assert sales_env.sales_service.get_sale(sale_id) is not None
    assert billing_service.get_invoice_for_sale(sale_id) is not None
    with session_scope() as session:
        stored = session.get(Invoice, invoice.id)
        assert stored is not None


def test_new_credit_sale_after_clearing_history_is_visible_again(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """El corte de "Borrar historial" es un timestamp — una factura nueva
    emitida DESPUÉS del corte sí debe aparecer normalmente, mientras la
    factura anterior (ya saldada) permanece oculta."""
    old_sale_id, old_amount = _complete_credit_sale(
        sales_env, quantity=Decimal(1), amount=Decimal(1000)
    )
    old_invoice = billing_service.generate_invoice(old_sale_id, credit_amount=old_amount)
    billing_service.register_payment(
        invoice_id=old_invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(1000),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )
    sales_env.customer_service.clear_credit_history(sales_env.customer_id)

    new_sale_id, new_amount = _complete_credit_sale(
        sales_env, quantity=Decimal(1), amount=Decimal(1000)
    )
    billing_service.generate_invoice(new_sale_id, credit_amount=new_amount)

    history = billing_service.list_customer_debt_history(sales_env.customer_id)
    assert len(history) == 1
    assert history[0].sale_id == new_sale_id
