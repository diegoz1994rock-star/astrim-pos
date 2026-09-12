"""Pruebas de UI de `SalesHistoryView` (backend `offscreen`): columnas de
cliente/documento con fallback "Sin nombre"/"Sin documento", la columna
"Medio de pago" (sincronizada con `SaleDTO.payments`, sin texto fijo), y
que el doble clic sobre una fila pida abrir el PDF de esa venta."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.sales.application.dto import SaleDTO, SalePaymentDTO
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus, SaleType
from pos.modules.sales.presentation.sales_history_view import SalesHistoryView


def _sale(
    sale_id: int,
    customer_name: str | None = None,
    customer_document: str | None = None,
    payments: list[SalePaymentDTO] | None = None,
) -> SaleDTO:
    return SaleDTO(
        id=sale_id,
        status=SaleStatus.COMPLETED,
        sale_type=SaleType.COUNTER,
        customer_id=None,
        subtotal=Decimal("1000"),
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("1000"),
        created_at=datetime.now(UTC),
        customer_name=customer_name,
        customer_document=customer_document,
        payments=payments or [],
    )


def _payment(method: PaymentMethod, amount: str = "1000") -> SalePaymentDTO:
    return SalePaymentDTO(id=1, payment_method=method, amount=Decimal(amount), reference=None)


def _make_view(qtbot: QtBot) -> SalesHistoryView:
    view = SalesHistoryView(Mock())
    qtbot.addWidget(view)
    return view


def test_missing_customer_name_and_document_show_placeholders(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_sales_loaded([_sale(1)])

    assert view._table.item(0, 4).text() == "Sin nombre"
    assert view._table.item(0, 5).text() == "Sin documento"


def test_present_customer_name_and_document_are_shown(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_sales_loaded([_sale(1, "Mario Gómez", "10203040")])

    assert view._table.item(0, 4).text() == "Mario Gómez"
    assert view._table.item(0, 5).text() == "10203040"


def test_payment_method_column_shows_label_for_each_method(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    sales = [
        _sale(1, payments=[_payment(PaymentMethod.CASH)]),
        _sale(2, payments=[_payment(PaymentMethod.CARD)]),
        _sale(3, payments=[_payment(PaymentMethod.QR)]),
        _sale(4, payments=[_payment(PaymentMethod.NEQUI)]),
        _sale(5, payments=[_payment(PaymentMethod.BRE_B)]),
    ]

    view._on_sales_loaded(sales)

    assert [view._table.item(row, 2).text() for row in range(5)] == [
        "Efectivo",
        "Tarjeta",
        "QR",
        "Nequi",
        "Bre-B",
    ]


def test_payment_method_column_joins_mixed_payments(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    mixed_sale = _sale(
        1, payments=[_payment(PaymentMethod.CASH, "500"), _payment(PaymentMethod.QR, "500")]
    )

    view._on_sales_loaded([mixed_sale])

    assert view._table.item(0, 2).text() == "Efectivo + QR"


def test_payment_method_column_shows_not_registered_for_sales_without_payments(
    qtbot: QtBot,
) -> None:
    view = _make_view(qtbot)

    view._on_sales_loaded([_sale(1)])

    assert view._table.item(0, 2).text() == "No registrado"


def test_double_click_opens_invoice_pdf(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_sales_loaded([_sale(1), _sale(2)])

    view._on_row_double_clicked(1, 0)

    view._view_model.open_invoice_pdf.assert_called_once_with(2)
