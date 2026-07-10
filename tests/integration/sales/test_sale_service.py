"""Pruebas de integración de SalesService contra SQLite real.

Cubren la orquestación crítica descrita en ARCHITECTURE.md §5b: stock,
caja y crédito deben reflejar el resultado de la venta atómicamente.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus
from pos.modules.sales.domain.events import SaleCompletedEvent, SaleVoidedEvent
from tests.integration.sales.conftest import SalesFixtures


def test_complete_sale_with_cash_payment(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("3"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("3000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.status is SaleStatus.COMPLETED
    assert sale.total == Decimal("3000")
    assert sale.items[0].quantity == Decimal("3")


def test_complete_sale_decreases_stock(sales_env: SalesFixtures) -> None:
    sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("10"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("10000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    remaining = sales_env.inventory_service.get_available_quantity(
        sales_env.product_id, sales_env.warehouse_id
    )
    assert remaining == Decimal("90")


def test_complete_sale_registers_cash_movement(sales_env: SalesFixtures) -> None:
    sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("2"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("2000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    expected = sales_env.cash_register_service.calculate_expected_amount(
        sales_env.cash_session_id
    )
    assert expected == Decimal("102000")


def test_complete_sale_computes_tax(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_with_tax_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1190"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.tax_total == Decimal("190.00")
    assert sale.total == Decimal("1190.00")


def test_complete_sale_with_insufficient_stock_is_rejected(sales_env: SalesFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1000"))],
            payments=[
                SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000000"))
            ],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            created_by_user_id=sales_env.user_id,
        )

    remaining = sales_env.inventory_service.get_available_quantity(
        sales_env.product_id, sales_env.warehouse_id
    )
    assert remaining == Decimal("100")


def test_complete_sale_with_mismatched_payment_total_is_rejected(
    sales_env: SalesFixtures,
) -> None:
    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
            payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1"))],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            created_by_user_id=sales_env.user_id,
        )


def test_complete_sale_with_credit_within_limit_charges_customer(
    sales_env: SalesFixtures,
) -> None:
    sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("5"))],
        payments=[
            SalePaymentInput(payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal("5000"))
        ],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=sales_env.customer_id,
        created_by_user_id=sales_env.user_id,
    )

    customers = sales_env.customer_service.list_customers()
    customer = next(c for c in customers if c.id == sales_env.customer_id)
    assert customer.current_debt == Decimal("5000")


def test_complete_sale_with_credit_exceeding_limit_is_rejected(sales_env: SalesFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("100"))],
            payments=[
                SalePaymentInput(
                    payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal("100000")
                )
            ],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            customer_id=sales_env.customer_id,
            created_by_user_id=sales_env.user_id,
        )
    remaining = sales_env.inventory_service.get_available_quantity(
        sales_env.product_id, sales_env.warehouse_id
    )
    assert remaining == Decimal("100")


def test_credit_payment_without_customer_is_rejected(sales_env: SalesFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
            payments=[
                SalePaymentInput(
                    payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal("1000")
                )
            ],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            created_by_user_id=sales_env.user_id,
        )


def test_complete_sale_with_closed_session_is_rejected(sales_env: SalesFixtures) -> None:
    sales_env.cash_register_service.close_session(
        cash_session_id=sales_env.cash_session_id,
        closed_by_user_id=sales_env.user_id,
        counted_amount=Decimal("100000"),
    )

    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.complete_sale(
            items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
            payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            created_by_user_id=sales_env.user_id,
        )


def test_complete_sale_publishes_event(sales_env: SalesFixtures) -> None:
    received: list[SaleCompletedEvent] = []
    sales_env.event_bus.subscribe(SaleCompletedEvent, received.append)

    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert len(received) == 1
    assert received[0].sale_id == sale.id


def test_void_sale_restores_stock(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("10"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("10000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    sales_env.sales_service.void_sale(
        sale_id=sale.id,
        warehouse_id=sales_env.warehouse_id,
        reason="Cliente se arrepintió",
        created_by_user_id=sales_env.user_id,
    )

    remaining = sales_env.inventory_service.get_available_quantity(
        sales_env.product_id, sales_env.warehouse_id
    )
    assert remaining == Decimal("100")


def test_void_sale_reverses_customer_credit(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("5"))],
        payments=[
            SalePaymentInput(payment_method=PaymentMethod.CUSTOMER_CREDIT, amount=Decimal("5000"))
        ],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        customer_id=sales_env.customer_id,
        created_by_user_id=sales_env.user_id,
    )

    sales_env.sales_service.void_sale(
        sale_id=sale.id,
        warehouse_id=sales_env.warehouse_id,
        reason=None,
        created_by_user_id=sales_env.user_id,
    )

    customers = sales_env.customer_service.list_customers()
    customer = next(c for c in customers if c.id == sales_env.customer_id)
    assert customer.current_debt == Decimal("0")


def test_void_sale_marks_status_refunded_and_publishes_event(sales_env: SalesFixtures) -> None:
    received: list[SaleVoidedEvent] = []
    sales_env.event_bus.subscribe(SaleVoidedEvent, received.append)

    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    voided = sales_env.sales_service.void_sale(
        sale_id=sale.id,
        warehouse_id=sales_env.warehouse_id,
        reason="prueba",
        created_by_user_id=sales_env.user_id,
    )

    assert voided.status is SaleStatus.REFUNDED
    assert len(received) == 1


def test_cannot_void_an_already_voided_sale(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    sales_env.sales_service.void_sale(
        sale_id=sale.id,
        warehouse_id=sales_env.warehouse_id,
        reason=None,
        created_by_user_id=sales_env.user_id,
    )

    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.void_sale(
            sale_id=sale.id,
            warehouse_id=sales_env.warehouse_id,
            reason=None,
            created_by_user_id=sales_env.user_id,
        )


def test_complete_sale_without_items_is_rejected(sales_env: SalesFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        sales_env.sales_service.complete_sale(
            items=[],
            payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("0"))],
            cash_session_id=sales_env.cash_session_id,
            warehouse_id=sales_env.warehouse_id,
            created_by_user_id=sales_env.user_id,
        )
