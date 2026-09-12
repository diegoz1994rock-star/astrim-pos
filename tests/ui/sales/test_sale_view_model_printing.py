"""Pruebas de `SaleViewModel.print_last_receipt`/`open_drawer_if_applicable`
con dependencias simuladas (`Mock`): reimprime vía la impresora asignada a
la caja activa (o el visor del sistema si no hay ninguna configurada), un
fallo de impresión nunca bloquea nada — solo se informa —, y
`open_drawer_after_print` solo dispara la apertura del cajón cuando el
propio flujo de "¿Desea imprimir?" lo pide (`trigger_drawer_if_configured=
True`), nunca en una reimpresión manual posterior."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
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


def _authenticate(view_model: SaleViewModel, user_id: int = 1, username: str = "cajero") -> None:
    view_model._session_manager.current = Mock(user_id=user_id, username=username)


def _complete_a_sale(
    view_model: SaleViewModel, *, sale_id: int = 555, cash_register_id: int = 7
) -> None:
    view_model._last_completed_sale_id = sale_id
    view_model._last_completed_cash_register_id = cash_register_id


def test_print_last_receipt_without_completed_sale_emits_error(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.print_last_receipt()

    assert "venta reciente" in errors[0]
    view_model._billing_service.generate_invoice.assert_not_called()


def test_print_last_receipt_falls_back_to_receipt_printer_without_configured_printer(
    qtbot: QtBot,
) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    _complete_a_sale(view_model)
    view_model._billing_service.generate_invoice.return_value = Mock(
        pdf_path="/tmp/x.pdf", invoice_number="F-000001", id=1,
    )
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.print_last_receipt()

    view_model._receipt_printer.print_receipt.assert_called_once()
    view_model._printer_service.print_document.assert_not_called()
    assert messages == ["Ticket enviado a impresión."]


def test_print_last_receipt_uses_configured_printer_when_available(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    _complete_a_sale(view_model)
    view_model._billing_service.generate_invoice.return_value = Mock(
        pdf_path="/tmp/x.pdf", invoice_number="F-000001", id=1,
    )
    configured_printer = Mock(id=9, name="Térmica Caja 1", open_drawer_after_print=False)
    view_model._printer_service.get_default_for_cash_register.return_value = configured_printer

    view_model.print_last_receipt()

    view_model._receipt_printer.print_receipt.assert_not_called()
    view_model._printer_service.print_document.assert_called_once()
    args, kwargs = view_model._printer_service.print_document.call_args
    assert args[0] == 9
    assert kwargs["user_id"] == 1


def test_print_failure_emits_error_and_never_raises(qtbot: QtBot) -> None:
    view_model = _make_view_model()
    _authenticate(view_model)
    _complete_a_sale(view_model)
    view_model._billing_service.generate_invoice.return_value = Mock(
        pdf_path="/tmp/x.pdf", invoice_number="F-000001", id=1,
    )
    configured_printer = Mock(id=9, name="Térmica Caja 1", open_drawer_after_print=True)
    view_model._printer_service.get_default_for_cash_register.return_value = configured_printer
    view_model._printer_service.print_document.side_effect = BusinessRuleViolationError(
        "puerto ocupado"
    )
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.print_last_receipt()  # no debe lanzar

    assert errors == ["puerto ocupado"]


def test_trigger_drawer_if_configured_true_opens_drawer_even_without_cash_payment(
    qtbot: QtBot,
) -> None:
    """Flujo real de "¿Desea imprimir?": si la impresora asignada tiene
    `open_drawer_after_print`, el cajón se abre después de imprimir aunque
    la venta no haya tenido ningún componente en efectivo."""
    view_model = _make_view_model()
    _authenticate(view_model)
    _complete_a_sale(view_model)
    view_model._billing_service.generate_invoice.return_value = Mock(
        pdf_path="/tmp/x.pdf", invoice_number="F-000001", id=1,
    )
    configured_printer = Mock(id=9, name="Térmica Caja 1", open_drawer_after_print=True)
    view_model._printer_service.get_default_for_cash_register.return_value = configured_printer
    sale = Mock(id=555, payments=[])  # sin componente en efectivo
    view_model._sales_service.get_sale.return_value = sale

    view_model.print_last_receipt(trigger_drawer_if_configured=True)
    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_called_once()


def test_manual_reprint_never_triggers_drawer_even_with_open_drawer_after_print(
    qtbot: QtBot,
) -> None:
    """Reimpresión manual (botón "Imprimir", `trigger_drawer_if_configured`
    en su valor por defecto `False`) nunca reabre el cajón, aunque la
    impresora asignada tenga `open_drawer_after_print` activado."""
    view_model = _make_view_model()
    _authenticate(view_model)
    _complete_a_sale(view_model)
    view_model._billing_service.generate_invoice.return_value = Mock(
        pdf_path="/tmp/x.pdf", invoice_number="F-000001", id=1,
    )
    configured_printer = Mock(id=9, name="Térmica Caja 1", open_drawer_after_print=True)
    view_model._printer_service.get_default_for_cash_register.return_value = configured_printer
    sale = Mock(id=555, payments=[])
    view_model._sales_service.get_sale.return_value = sale

    view_model.print_last_receipt()  # sin trigger_drawer_if_configured
    view_model.open_drawer_if_applicable()

    view_model._cash_drawer_service.open_drawer_for_cash_register.assert_not_called()
