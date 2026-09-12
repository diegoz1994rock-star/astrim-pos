"""Un abono a una factura de crédito en efectivo debe intentar abrir el
cajón monedero de la caja donde se registró; un abono electrónico nunca
debe intentarlo. Usa el `CashDrawerService` real (no mockeado) de
`conftest.py` — sin hardware real conectado, el intento falla honesto y
queda registrado, pero el abono en sí nunca se revierte ni bloquea."""

from __future__ import annotations

from decimal import Decimal

from pos.modules.billing.application.billing_service import BillingService
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_drawers.domain.enums import CashDrawerEventType, CashDrawerOpeningKind
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures

_NO_HARDWARE_PORT = "/dev/tty.no-existe-nunca"


def _complete_credit_sale(sales_env: SalesFixtures) -> int:
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
    return sale.id


def test_cash_debt_payment_attempts_to_open_the_drawer(
    sales_env: SalesFixtures,
    billing_service: BillingService,
    cash_drawer_service: CashDrawerService,
) -> None:
    default_register = sales_env.cash_register_service.list_registers()[0]
    drawer = cash_drawer_service.create_device(
        name="Cajón Abonos", port=_NO_HARDWARE_PORT, cash_register_id=default_register.id,
        auto_open_after_sale=True,
    )
    sale_id = _complete_credit_sale(sales_env)
    invoice = billing_service.generate_invoice(sale_id, credit_amount=Decimal(2000))

    receipt = billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(500),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )

    assert receipt.amount == Decimal(500)  # el abono se registró sin importar el cajón
    events = cash_drawer_service.list_events(drawer.id)
    assert len(events) == 1
    assert events[0].event_type is CashDrawerEventType.OPEN_FAILED
    assert events[0].opening_kind is CashDrawerOpeningKind.AUTOMATIC
    assert events[0].invoice_id == invoice.id
    assert events[0].debt_payment_id is not None
    assert events[0].reason == "Abono en efectivo"


def test_electronic_debt_payment_never_attempts_to_open_the_drawer(
    sales_env: SalesFixtures,
    billing_service: BillingService,
    cash_drawer_service: CashDrawerService,
) -> None:
    default_register = sales_env.cash_register_service.list_registers()[0]
    drawer = cash_drawer_service.create_device(
        name="Cajón Abonos", port=_NO_HARDWARE_PORT, cash_register_id=default_register.id,
        auto_open_after_sale=True,
    )
    sale_id = _complete_credit_sale(sales_env)
    invoice = billing_service.generate_invoice(sale_id, credit_amount=Decimal(2000))

    billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(500),
        payment_method=PaymentMethod.TRANSFER,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )

    assert cash_drawer_service.list_events(drawer.id) == []


def test_cash_debt_payment_without_matching_drawer_does_not_fail(
    sales_env: SalesFixtures, billing_service: BillingService,
) -> None:
    """Sin ningún cajón configurado para esa caja, el abono en efectivo
    debe seguir funcionando con normalidad — no todo negocio tiene uno."""
    sale_id = _complete_credit_sale(sales_env)
    invoice = billing_service.generate_invoice(sale_id, credit_amount=Decimal(2000))

    receipt = billing_service.register_payment(
        invoice_id=invoice.id,
        customer_id=sales_env.customer_id,
        amount=Decimal(500),
        payment_method=PaymentMethod.CASH,
        cash_session_id=sales_env.cash_session_id,
        created_by_user_id=sales_env.user_id,
    )

    assert receipt.amount == Decimal(500)
