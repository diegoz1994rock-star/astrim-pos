"""Pruebas de integración de SalesService contra SQLite real.

Cubren la orquestación crítica descrita en ARCHITECTURE.md §5b: stock,
caja y crédito deben reflejar el resultado de la venta atómicamente.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from pos.core.database.base import today_utc_bounds
from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.products.infrastructure.models import Tax
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus
from pos.modules.sales.domain.events import SaleCompletedEvent, SaleVoidedEvent
from pos.modules.sales.infrastructure.models import Sale
from pos.modules.users.infrastructure.models import User
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


def test_complete_sale_persists_customer_name_and_document(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
        customer_name="  Mario Gómez  ",
        customer_document="  10203040  ",
    )

    assert sale.customer_name == "Mario Gómez"
    assert sale.customer_document == "10203040"


def test_complete_sale_without_customer_name_leaves_it_null(sales_env: SalesFixtures) -> None:
    """Los campos son opcionales — no se les aplica ningún valor por
    defecto tipo "Consumidor Final" acá (ese fallback a texto vive en
    `billing_service`, no en `sales`)."""
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.customer_name is None
    assert sale.customer_document is None


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


def test_complete_sale_computes_tax_from_active_taxes(sales_env: SalesFixtures) -> None:
    """El impuesto ya no se elige por producto: se aplica la suma de todos
    los impuestos activos (administrados en Administración → Impuestos) a
    toda la venta por igual."""
    with session_scope() as session:
        session.add(Tax(name="IVA-TEST", rate_percent=Decimal("19")))

    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1190"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.tax_total == Decimal("190.00")
    assert sale.total == Decimal("1190.00")


def test_complete_sale_has_no_tax_when_no_active_taxes(sales_env: SalesFixtures) -> None:
    with session_scope() as session:
        session.add(Tax(name="IVA-INACTIVO", rate_percent=Decimal("19"), is_active=False))

    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.tax_total == Decimal("0.00")
    assert sale.total == Decimal("1000.00")


def test_complete_sale_allows_selling_more_than_one_warehouse_holds(
    sales_env: SalesFixtures,
) -> None:
    """El inventario general (`sales_env.product_id` tiene 100 en la
    bodega por defecto) alcanza aunque se agregue otra bodega vacía — la
    venta se reparte entre bodegas en vez de fallar por una sola."""
    other_warehouse = sales_env.inventory_service.create_warehouse(name="Bodega Secundaria")
    sales_env.inventory_service.register_entry(
        product_id=sales_env.product_id,
        warehouse_id=other_warehouse.id,
        quantity=Decimal("20"),
        reason="Stock adicional de prueba",
        created_by_user_id=None,
    )

    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("110"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("110000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.status is SaleStatus.COMPLETED
    remaining_default = sales_env.inventory_service.get_available_quantity(
        sales_env.product_id, sales_env.warehouse_id
    )
    remaining_other = sales_env.inventory_service.get_available_quantity(
        sales_env.product_id, other_warehouse.id
    )
    assert remaining_default == Decimal("0")
    assert remaining_other == Decimal("10")


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


def test_complete_sale_persists_line_note(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[
            SaleItemInput(
                product_id=sales_env.product_id, quantity=Decimal("2"), note="Sin empacar"
            )
        ],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("2000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.items[0].note == "Sin empacar"


def test_complete_sale_exposes_created_by_user_id(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.created_by_user_id == sales_env.user_id


def test_complete_sale_publishes_event_with_created_by_user_id(sales_env: SalesFixtures) -> None:
    received: list[SaleCompletedEvent] = []
    sales_env.event_bus.subscribe(SaleCompletedEvent, received.append)

    sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert len(received) == 1
    assert received[0].created_by_user_id == sales_env.user_id


def test_void_sale_publishes_event_with_voided_by_user_id(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    received: list[SaleVoidedEvent] = []
    sales_env.event_bus.subscribe(SaleVoidedEvent, received.append)

    sales_env.sales_service.void_sale(
        sale_id=sale.id,
        warehouse_id=sales_env.warehouse_id,
        reason="Cliente se arrepintió",
        created_by_user_id=sales_env.user_id,
    )

    assert len(received) == 1
    assert received[0].voided_by_user_id == sales_env.user_id
    assert received[0].reason == "Cliente se arrepintió"


@pytest.mark.parametrize(
    "method",
    [
        PaymentMethod.CARD,
        PaymentMethod.NEQUI,
        PaymentMethod.DAVIPLATA,
        PaymentMethod.BRE_B,
    ],
)
def test_complete_sale_accepts_new_payment_methods(
    sales_env: SalesFixtures, method: PaymentMethod
) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal("1"))],
        payments=[SalePaymentInput(payment_method=method, amount=Decimal("1000"))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    assert sale.status is SaleStatus.COMPLETED
    assert sale.payments[0].payment_method is method


def test_get_daily_totals_sums_only_completed_sales_in_range(sales_env: SalesFixtures) -> None:
    sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(2))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(2000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    voided_sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(1))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(1000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    sales_env.sales_service.void_sale(
        sale_id=voided_sale.id,
        warehouse_id=sales_env.warehouse_id,
        reason=None,
        created_by_user_id=sales_env.user_id,
    )

    start, end = today_utc_bounds()
    totals = sales_env.sales_service.get_daily_totals(start, end)

    assert totals.total == Decimal(2000)
    assert len(totals.by_cashier) == 1
    assert totals.by_cashier[0].user_id == sales_env.user_id
    assert totals.by_cashier[0].total == Decimal(2000)


def test_get_daily_totals_excludes_sales_outside_the_range(sales_env: SalesFixtures) -> None:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(1))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(1000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    with session_scope() as session:
        stored = session.get(Sale, sale.id)
        assert stored is not None
        stored.created_at = stored.created_at - timedelta(days=2)

    start, end = today_utc_bounds()
    totals = sales_env.sales_service.get_daily_totals(start, end)

    assert totals.total == Decimal(0)
    assert totals.by_cashier == []


def test_get_daily_totals_groups_by_multiple_cashiers(sales_env: SalesFixtures) -> None:
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

    sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(1))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(1000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(2))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(2000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=other_user_id,
    )

    start, end = today_utc_bounds()
    totals = sales_env.sales_service.get_daily_totals(start, end)

    totals_by_user = {c.user_id: c.total for c in totals.by_cashier}
    assert totals_by_user[sales_env.user_id] == Decimal(1000)
    assert totals_by_user[other_user_id] == Decimal(2000)
    assert totals.total == Decimal(3000)
