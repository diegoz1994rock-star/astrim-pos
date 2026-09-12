"""Pruebas de `SaleViewModel.open_drawer_if_applicable` con dependencias
simuladas (`Mock`): abre el cajón únicamente cuando la venta tuvo un
componente en efectivo, nunca en tarjeta/QR/Nequi/Bre-B/crédito 100%
electrónico, y un fallo del cajón nunca se propaga como una excepción ni
revierte nada — solo se informa."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.cash_drawers.domain.enums import CashDrawerOpeningKind
from pos.modules.sales.application.dto import SalePaymentDTO
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.sales.presentation.sale_view_model import SaleViewModel


def _make_view_model() -> SaleViewModel:
    sales_service = Mock()
    inventory_service = Mock()
    inventory_service.list_warehouses.return_value = [Mock(id=1)]
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = [Mock(id=7)]
    printer_service = Mock()
    printer_service.get_default_for_cash_register.return_value = None
    view_model = SaleViewModel(
        sales_service,
        Mock(),  # product_service
        Mock(),  # customer_service
        inventory_service,
        cash_register_service,
        Mock(),  # session_manager
        Mock(),  # billing_service
        Mock(),  # receipt_printer
        Mock(),  # cash_drawer_service
        Mock(),  # qr_payment_service
        Mock(),  # restaurant_service
        Mock(),  # scale_read_service
        Mock(),  # nequi_payment_service
        Mock(),  # breb_payment_service
        Mock(),  # barcode_read_service
        printer_service,
    )
    return view_model


def _sale_with_payments(*payments: SalePaymentDTO, sale_id: int = 555):
    return Mock(id=sale_id, payments=list(payments), items=[])


def _payment(method: PaymentMethod, amount: str) -> SalePaymentDTO:
    return SalePaymentDTO(id=1, payment_method=method, amount=Decimal(amount), reference=None)


def _authenticate(view_model: SaleViewModel, user_id: int = 1, username: str = "cajero") -> None:
    view_model._session_manager.current = Mock(user_id=user_id, username=username)


def _complete_a_sale(view_model: SaleViewModel, sale) -> None:
    """Deja el view model en el mismo estado que queda después de
    `complete_sale()` — sin depender de esa ruta completa, que ya se
    prueba por separado en `test_sale_view_model.py`."""
    view_model._last_completed_sale_id = sale.id
    view_model._last_completed_cash_register_id = 7
    view_model._sales_service.get_sale.return_value = sale


def test_cash_sale_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(_payment(PaymentMethod.CASH, "50000"))
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_called_once_with(
        7, user_id=1, username="cajero", opening_kind=CashDrawerOpeningKind.AUTOMATIC,
        sale_id=555,
    )


def test_card_sale_never_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(_payment(PaymentMethod.CARD, "50000"))
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()


def test_qr_sale_never_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(_payment(PaymentMethod.QR, "50000"))
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()


def test_nequi_sale_never_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(_payment(PaymentMethod.NEQUI, "50000"))
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()


def test_bre_b_sale_never_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(_payment(PaymentMethod.BRE_B, "50000"))
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()


def test_customer_credit_sale_never_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(_payment(PaymentMethod.CUSTOMER_CREDIT, "50000"))
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()


def test_mixed_payment_with_cash_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(
        _payment(PaymentMethod.CASH, "20000"), _payment(PaymentMethod.CARD, "30000")
    )
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_called_once()


def test_mixed_payment_without_cash_never_opens_the_drawer(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(
        _payment(PaymentMethod.CARD, "20000"), _payment(PaymentMethod.QR, "30000")
    )
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()


def test_drawer_failure_does_not_raise_and_reports_error(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    sale = _sale_with_payments(_payment(PaymentMethod.CASH, "50000"))
    _complete_a_sale(view_model, sale)
    view_model._cash_drawer_service.open_drawer_for_cash_register.side_effect = (
        BusinessRuleViolationError("el cajón no respondió")
    )
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.open_drawer_if_applicable()  # no debe lanzar

    assert len(errors) == 1
    assert "el cajón no respondió" in errors[0]


def test_no_completed_sale_does_nothing(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()
    view_model._sales_service.get_sale.assert_not_called()


def test_without_authenticated_user_does_nothing(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    view_model._session_manager.current = None
    sale = _sale_with_payments(_payment(PaymentMethod.CASH, "50000"))
    _complete_a_sale(view_model, sale)

    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()


def test_reprinting_a_receipt_never_opens_the_drawer(qtbot: QtBot) -> None:
    """`print_last_receipt` (botón "Imprimir"/reimpresión) ya no llama a
    ninguna apertura — la apertura automática ocurre una sola vez, al
    completar la venta."""
    view_model = _make_view_model()
    view_model._last_completed_sale_id = 555
    view_model._billing_service.generate_invoice.return_value = Mock(pdf_path="/tmp/x.pdf")

    view_model.print_last_receipt()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()
    view_model._cash_drawer_service.open_drawer.assert_not_called()
