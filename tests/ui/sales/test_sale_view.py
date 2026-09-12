"""Pruebas de UI de `SaleView` (backend `offscreen`): escaneo de código,
combo de productos con autocompletado, ayuda visual de venta por peso,
edición del carrito (un solo diálogo para cantidad/precio/nota) y cálculo
de cambio en efectivo.

Los métodos `_show_error`/`_show_info` se reemplazan por un `Mock` en cada
prueba que pueda dispararlos: `QMessageBox.warning/information` son
modales bloqueantes (mismo problema ya visto con `MovementDialog`) y
colgarían la prueba esperando un clic que nunca llega. Lo mismo para
`QMessageBox.question` en la confirmación de "Eliminar producto"."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QMessageBox
from pytestqt.qtbot import QtBot

from pos.modules.barcode_scanners.application.dto import BarcodeReadResultDTO, BarcodeSettingsDTO
from pos.modules.barcode_scanners.domain.enums import BarcodeSymbology
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.sales.application.dto import SalePreviewDTO, SalePreviewLineDTO
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.sales.presentation import sale_view as sale_view_module
from pos.modules.sales.presentation.sale_view import SaleView
from pos.modules.scales.domain.enums import WeightEntrySource

_DEFAULT_BARCODE_SETTINGS = BarcodeSettingsDTO(
    reader_enabled=True,
    auto_enter_enabled=True,
    duplicate_debounce_ms=150,
    sound_on_success=True,
    sound_on_not_found=True,
    show_visual_notification=True,
)


def _found_result(product: ProductDTO, code: str = "7701234567890") -> BarcodeReadResultDTO:
    return BarcodeReadResultDTO(
        code=code, symbology=BarcodeSymbology.EAN13, found=True, product=product,
        ignored=False, reason=None,
    )


def _not_found_result(code: str) -> BarcodeReadResultDTO:
    return BarcodeReadResultDTO(
        code=code, symbology=BarcodeSymbology.UNKNOWN, found=False, product=None,
        ignored=False, reason=None,
    )


def _ignored_result(code: str, reason: str) -> BarcodeReadResultDTO:
    return BarcodeReadResultDTO(
        code=code, symbology=BarcodeSymbology.UNKNOWN, found=False, product=None,
        ignored=True, reason=reason,
    )

_UNIT_PRODUCT = ProductDTO(
    id=1,
    sku="SKU-1",
    name="Producto Unidad",
    description=None,
    category_id=None,
    category_name=None,
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("1000"),
    cost_price=Decimal("500"),
    unit_of_measure="unidad",
    is_active=True,
    track_inventory=True,
)
_WEIGHT_PRODUCT = ProductDTO(
    id=2,
    sku="SKU-2",
    name="Queso",
    description=None,
    category_id=None,
    category_name=None,
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("8000"),
    cost_price=Decimal("4000"),
    unit_of_measure="kg",
    is_active=True,
    track_inventory=True,
    sale_unit=SaleUnit.WEIGHT,
)
_BARCODE_PRODUCT = ProductDTO(
    id=3,
    sku="SKU-3",
    name="Martillo 5K",
    description=None,
    category_id=None,
    category_name=None,
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("25000"),
    cost_price=Decimal("15000"),
    unit_of_measure="unidad",
    is_active=True,
    track_inventory=True,
    barcodes=("7701234567890",),
)
_WEIGHT_BARCODE_PRODUCT = ProductDTO(
    id=4,
    sku="SKU-4",
    name="Jamón",
    description=None,
    category_id=None,
    category_name=None,
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("12000"),
    cost_price=Decimal("6000"),
    unit_of_measure="kg",
    is_active=True,
    track_inventory=True,
    sale_unit=SaleUnit.WEIGHT,
    barcodes=("7709876543210",),
)


def _make_view(qtbot: QtBot) -> SaleView:
    view = SaleView(Mock())
    view._view_model.get_barcode_settings.return_value = _DEFAULT_BARCODE_SETTINGS
    qtbot.addWidget(view)
    view._on_products_loaded(
        [_UNIT_PRODUCT, _WEIGHT_PRODUCT, _BARCODE_PRODUCT, _WEIGHT_BARCODE_PRODUCT]
    )
    return view


def test_on_scan_entered_delegates_to_view_model_scan_barcode(qtbot: QtBot) -> None:
    """La resolución real (buscar el producto, evitar rebote, registrar la
    lectura) vive en `BarcodeReadService`/`SaleViewModel.scan_barcode` — la
    vista solo entrega el texto tal cual, sin volver a implementar esa
    lógica (ver auditoría del módulo de código de barras)."""
    view = _make_view(qtbot)

    view._scan_edit.setText("7701234567890")
    view._on_scan_entered()

    view._view_model.scan_barcode.assert_called_once_with("7701234567890")


def test_on_scan_entered_ignores_empty_text(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._scan_edit.setText("   ")
    view._on_scan_entered()

    view._view_model.scan_barcode.assert_not_called()


def _tab_key_event() -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)


def test_tab_on_empty_scan_field_holds_the_current_sale(qtbot: QtBot) -> None:
    """Comportamiento existente preservado: `Tab` con el campo vacío es el
    atajo deliberado del cajero para dejar la venta en espera."""
    view = _make_view(qtbot)
    view._scan_edit.setText("")

    consumed = view.eventFilter(view._scan_edit, _tab_key_event())

    assert consumed is True
    view._view_model.hold_current_sale.assert_called_once()
    view._view_model.scan_barcode.assert_not_called()


def test_tab_with_pending_scan_text_resolves_the_scan_instead_of_holding(qtbot: QtBot) -> None:
    """Hallazgo de la certificación: algunos lectores HID se configuran
    para terminar con Tab en vez de Enter — si el campo tiene texto sin
    procesar, Tab debe resolver el escaneo, no interpretarse como el
    atajo de "dejar en espera" (que dejaría el código sin agregar)."""
    view = _make_view(qtbot)
    view._scan_edit.setText("7701234567890")

    consumed = view.eventFilter(view._scan_edit, _tab_key_event())

    assert consumed is True
    view._view_model.scan_barcode.assert_called_once_with("7701234567890")
    view._view_model.hold_current_sale.assert_not_called()


def test_scan_resolved_found_clears_and_refocuses_field(qtbot: QtBot) -> None:
    """El carrito ya lo actualizó `SaleViewModel.scan_barcode` (llama a
    `add_item` internamente) — acá solo se verifica la reacción de la
    vista: limpiar y devolver el foco, sin abrir nada. `hasFocus()` real
    requiere activación de ventana a nivel de sistema operativo, poco
    confiable en el backend `offscreen` (ver `test_products_view.py`), así
    que se verifica `setFocus()` mockeado en vez del foco real."""
    view = _make_view(qtbot)
    view._scan_edit.setText("7701234567890")
    view._scan_edit.setFocus = Mock()

    view._on_scan_resolved(_found_result(_BARCODE_PRODUCT))

    assert view._scan_edit.text() == ""
    view._scan_edit.setFocus.assert_called_once()
    assert view._scan_quantity_edit.isHidden()


def test_scan_resolved_found_for_weight_product_opens_scale_dialog(
    qtbot: QtBot, monkeypatch
) -> None:
    """Un producto por peso escaneado por código de barras (match exacto,
    `result.found=True`) abre `ScaleWeightDialog` para leer/ingresar el
    peso real — el ViewModel no agregó nada al carrito para este caso (ver
    `SaleViewModel.scan_barcode`), así que la vista debe abrir el diálogo
    en vez de solo mostrar el aviso de "agregado"."""
    view = _make_view(qtbot)
    opened = []
    monkeypatch.setattr(
        sale_view_module.SaleView, "_open_scale_weight_dialog", lambda self, p: opened.append(p)
    )

    view._on_scan_resolved(_found_result(_WEIGHT_BARCODE_PRODUCT, code="7709876543210"))

    assert opened == [_WEIGHT_BARCODE_PRODUCT]
    assert view._scan_edit.text() == ""


def test_scan_resolved_ignored_clears_and_refocuses_without_adding(qtbot: QtBot) -> None:
    """`hasFocus()` real requiere activación de ventana a nivel de sistema
    operativo, poco confiable en el backend `offscreen` (ver
    `test_products_view.py`), así que se verifica `setFocus()` mockeado en
    vez del foco real."""
    view = _make_view(qtbot)
    view._scan_edit.setText("7701234567890")
    view._scan_edit.setFocus = Mock()

    view._on_scan_resolved(
        _ignored_result("7701234567890", "Lectura duplicada (rebote del lector).")
    )

    assert view._scan_edit.text() == ""
    view._scan_edit.setFocus.assert_called_once()


def test_scan_resolved_not_found_known_sku_shows_quantity_field_without_adding(
    qtbot: QtBot,
) -> None:
    view = _make_view(qtbot)

    view._on_scan_resolved(_not_found_result("SKU-1"))

    view._view_model.add_item.assert_not_called()
    assert not view._scan_quantity_edit.isHidden()
    assert view._scan_edit.text() == ""


def test_scan_quantity_entered_adds_item_with_given_quantity(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_scan_resolved(_not_found_result("SKU-1"))
    view._scan_quantity_edit.setText("5")
    view._on_scan_quantity_entered()

    view._view_model.add_item.assert_called_once_with(1, Decimal("5"))
    assert view._scan_quantity_edit.isHidden()
    assert view._scan_pending_label.isHidden()


class _FakeScaleWeightDialog:
    """Reemplaza el diálogo real (evita abrir un `QDialog.exec()` modal
    bloqueante en la prueba, mismo problema ya visto con `QrPaymentDialog`)."""

    result = QDialog.DialogCode.Accepted
    DialogCode = QDialog.DialogCode
    weight_to_return = Decimal("1.5")

    def __init__(self, **kwargs: object) -> None:
        pass

    def exec(self) -> QDialog.DialogCode:
        return self.result

    def weight(self) -> Decimal:
        return self.weight_to_return

    def weight_entry_source(self) -> WeightEntrySource:
        return WeightEntrySource.MANUAL


def test_scan_partial_name_match_for_weight_product_opens_scale_dialog(
    qtbot: QtBot, monkeypatch
) -> None:
    """"Queso" (`_WEIGHT_PRODUCT`) no matchea por código de barras (no es un
    código exacto) y cae al camino manual por nombre — ese camino, al no
    tratarse de un escaneo real, sigue abriendo `ScaleWeightDialog` para
    pedir el peso."""
    view = _make_view(qtbot)
    _FakeScaleWeightDialog.result = QDialog.DialogCode.Accepted
    monkeypatch.setattr(sale_view_module, "ScaleWeightDialog", _FakeScaleWeightDialog)

    view._on_scan_resolved(_not_found_result("Queso"))

    view._view_model.add_item.assert_called_once_with(
        2, Decimal("1.5"), weight_entry_source=WeightEntrySource.MANUAL
    )


def test_scan_unknown_sku_shows_error(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._show_error = Mock()

    view._on_scan_resolved(_not_found_result("NOPE"))

    view._view_model.add_item.assert_not_called()
    view._show_error.assert_called_once()
    assert view._scan_edit.text() == ""


def test_product_combo_has_completer_for_quick_search(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert view._product_combo.isEditable()
    assert view._product_combo.completer() is not None


def test_quantity_placeholder_reflects_weight_based_product(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._product_combo.setCurrentIndex(1)  # _WEIGHT_PRODUCT ("kg")
    assert "kg" in view._quantity_edit.placeholderText()

    view._product_combo.setCurrentIndex(0)  # _UNIT_PRODUCT ("unidad")
    assert view._quantity_edit.placeholderText() == "Cantidad"


def test_edit_and_remove_buttons_disabled_without_cart_selection(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    assert not view._edit_item_button.isEnabled()
    assert not view._remove_item_button.isEnabled()


def test_edit_item_without_cart_selection_shows_error(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._show_error = Mock()

    view._on_edit_item_clicked()

    view._show_error.assert_called_once()
    view._view_model.update_item.assert_not_called()


def test_remove_item_without_cart_selection_shows_error(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._show_error = Mock()

    view._on_remove_item_clicked()

    view._show_error.assert_called_once()
    view._view_model.remove_item.assert_not_called()


def test_remove_item_asks_confirmation_and_removes_on_yes(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    preview = SalePreviewDTO(
        subtotal=Decimal("1000"),
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("1000"),
        items=[
            SalePreviewLineDTO(
                product_id=1,
                product_name="Producto Unidad",
                quantity=Decimal("1"),
                unit_price=Decimal("1000"),
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                line_total=Decimal("1000"),
            )
        ],
    )
    view._on_cart_changed(preview)
    view._items_table.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.StandardButton.Yes))

    view._on_remove_item_clicked()

    view._view_model.remove_item.assert_called_once_with(0)


def test_remove_item_cancelled_confirmation_does_not_remove(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    preview = SalePreviewDTO(
        subtotal=Decimal("1000"),
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("1000"),
        items=[
            SalePreviewLineDTO(
                product_id=1,
                product_name="Producto Unidad",
                quantity=Decimal("1"),
                unit_price=Decimal("1000"),
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                line_total=Decimal("1000"),
            )
        ],
    )
    view._on_cart_changed(preview)
    view._items_table.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.StandardButton.No))

    view._on_remove_item_clicked()

    view._view_model.remove_item.assert_not_called()


def test_items_table_columns_have_no_note_and_rename_total(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    headers = [
        view._items_table.horizontalHeaderItem(i).text()
        for i in range(view._items_table.columnCount())
    ]
    assert headers == ["Producto", "Cantidad / Peso", "Precio", "Impuesto", "Total"]
    assert "Nota" not in headers


def test_cart_row_formats_weight_line_as_weight_not_units(qtbot: QtBot) -> None:
    """El carrito nunca debe mostrar una línea por peso como si fueran "2
    unidades" — cantidad y precio deben leerse explícitamente como peso."""
    view = _make_view(qtbot)
    preview = SalePreviewDTO(
        subtotal=Decimal("18800"),
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("18800"),
        items=[
            SalePreviewLineDTO(
                product_id=1,
                product_name="Papa",
                quantity=Decimal("2.350"),
                unit_price=Decimal("8000"),
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                line_total=Decimal("18800"),
                sale_unit=SaleUnit.WEIGHT,
                unit_of_measure="kg",
            )
        ],
    )

    view._on_cart_changed(preview)

    assert view._items_table.item(0, 1).text() == "2.350 kg"
    assert "kg" in view._items_table.item(0, 2).text()
    assert "8.000" in view._items_table.item(0, 2).text() or "8000" in view._items_table.item(
        0, 2
    ).text()


def test_cart_row_formats_unit_line_as_plain_quantity(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    preview = SalePreviewDTO(
        subtotal=Decimal("2000"),
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("2000"),
        items=[
            SalePreviewLineDTO(
                product_id=1,
                product_name="Martillo",
                quantity=Decimal("2"),
                unit_price=Decimal("1000"),
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                line_total=Decimal("2000"),
            )
        ],
    )

    view._on_cart_changed(preview)

    assert view._items_table.item(0, 1).text() == "2"
    assert "/" not in view._items_table.item(0, 2).text()


def test_payment_combo_shows_only_the_five_manual_methods(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    combo = view._payment_method_combo
    methods = [combo.itemData(i) for i in range(combo.count())]
    assert methods == [
        PaymentMethod.CASH,
        PaymentMethod.CARD,
        PaymentMethod.QR,
        PaymentMethod.NEQUI,
        PaymentMethod.BRE_B,
    ]
    assert PaymentMethod.TRANSFER not in methods
    assert PaymentMethod.DAVIPLATA not in methods
    assert PaymentMethod.CUSTOMER_CREDIT not in methods
    assert PaymentMethod.OTHER not in methods


def _preview_with_total(total: Decimal) -> SalePreviewDTO:
    return SalePreviewDTO(
        subtotal=total, discount_total=Decimal("0"), tax_total=Decimal("0"), total=total, items=[]
    )


def test_cash_payment_over_total_shows_change_and_caps_applied_amount(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("10000")))
    cash_index = view._payment_method_combo.findData(PaymentMethod.CASH)
    view._payment_method_combo.setCurrentIndex(cash_index)
    view._payment_amount_edit.setText("15000")

    view._on_add_payment_clicked()

    assert "5.000" in view._change_label.text()
    view._view_model.add_payment.assert_called_once_with(PaymentMethod.CASH, Decimal("10000"))


def test_cash_payment_entering_enter_key_behaves_like_button(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("10000")))
    view._payment_amount_edit.setText("10000")

    view._payment_amount_edit.returnPressed.emit()

    view._view_model.add_payment.assert_called_once_with(PaymentMethod.CASH, Decimal("10000"))


def test_payment_amount_not_a_number_shows_error(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._show_error = Mock()
    view._payment_amount_edit.setText("abc")

    view._on_add_payment_clicked()

    view._show_error.assert_called_once()
    view._view_model.add_payment.assert_not_called()


def test_selecting_qr_method_switches_to_qr_payment_page(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    qr_index = view._payment_method_combo.findData(PaymentMethod.QR)
    view._payment_method_combo.setCurrentIndex(qr_index)
    assert view._payment_stack.currentWidget() is view._qr_pay_button.parentWidget()

    cash_index = view._payment_method_combo.findData(PaymentMethod.CASH)
    view._payment_method_combo.setCurrentIndex(cash_index)
    assert view._payment_stack.currentWidget() is view._payment_amount_edit.parentWidget()


class _FakeManualPaymentDialog:
    """Reemplaza el diálogo real (evita abrir un `QDialog.exec()` modal
    bloqueante en la prueba, mismo problema ya visto con `QMessageBox`)."""

    last_total: Decimal | None = None
    result = QDialog.DialogCode.Accepted
    reference = "REF-TEST"
    DialogCode = QDialog.DialogCode

    def __init__(self, *, total: Decimal, parent: object = None, **_kwargs: object) -> None:
        type(self).last_total = total

    def exec(self) -> QDialog.DialogCode:
        return self.result


class _FakeQrPaymentDialog(_FakeManualPaymentDialog):
    pass


class _FakeNequiPaymentDialog(_FakeManualPaymentDialog):
    pass


class _FakeBreBPaymentDialog(_FakeManualPaymentDialog):
    pass


def test_qr_pay_accepted_adds_payment_for_remaining_total(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    _FakeQrPaymentDialog.result = QDialog.DialogCode.Accepted
    monkeypatch.setattr(sale_view_module, "QrPaymentDialog", _FakeQrPaymentDialog)

    view._on_qr_pay_clicked()

    assert _FakeQrPaymentDialog.last_total == Decimal("20000")
    view._view_model.add_payment.assert_called_once_with(
        PaymentMethod.QR, Decimal("20000"), reference="REF-TEST"
    )


def test_qr_pay_cancelled_does_not_add_payment(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    _FakeQrPaymentDialog.result = QDialog.DialogCode.Rejected
    monkeypatch.setattr(sale_view_module, "QrPaymentDialog", _FakeQrPaymentDialog)

    view._on_qr_pay_clicked()

    view._view_model.add_payment.assert_not_called()


def test_qr_pay_with_nothing_pending_shows_error(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._show_error = Mock()
    view._on_cart_changed(_preview_with_total(Decimal("0")))

    view._on_qr_pay_clicked()

    view._show_error.assert_called_once()
    view._view_model.add_payment.assert_not_called()


def test_nequi_pay_accepted_adds_payment_for_remaining_total(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    _FakeNequiPaymentDialog.result = QDialog.DialogCode.Accepted
    monkeypatch.setattr(sale_view_module, "NequiPaymentDialog", _FakeNequiPaymentDialog)

    view._on_nequi_pay_clicked()

    assert _FakeNequiPaymentDialog.last_total == Decimal("20000")
    view._view_model.add_payment.assert_called_once_with(
        PaymentMethod.NEQUI, Decimal("20000"), reference="REF-TEST"
    )


def test_nequi_pay_cancelled_does_not_add_payment(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    _FakeNequiPaymentDialog.result = QDialog.DialogCode.Rejected
    monkeypatch.setattr(sale_view_module, "NequiPaymentDialog", _FakeNequiPaymentDialog)

    view._on_nequi_pay_clicked()

    view._view_model.add_payment.assert_not_called()


def test_breb_pay_accepted_adds_payment_for_remaining_total(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    _FakeBreBPaymentDialog.result = QDialog.DialogCode.Accepted
    monkeypatch.setattr(sale_view_module, "BreBPaymentDialog", _FakeBreBPaymentDialog)

    view._on_breb_pay_clicked()

    assert _FakeBreBPaymentDialog.last_total == Decimal("20000")
    view._view_model.add_payment.assert_called_once_with(
        PaymentMethod.BRE_B, Decimal("20000"), reference="REF-TEST"
    )


def test_breb_pay_cancelled_does_not_add_payment(qtbot: QtBot, monkeypatch) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    _FakeBreBPaymentDialog.result = QDialog.DialogCode.Rejected
    monkeypatch.setattr(sale_view_module, "BreBPaymentDialog", _FakeBreBPaymentDialog)

    view._on_breb_pay_clicked()

    view._view_model.add_payment.assert_not_called()


def test_complete_clicked_opens_manual_dialog_when_method_needs_it(
    qtbot: QtBot, monkeypatch
) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    qr_index = view._payment_method_combo.findData(PaymentMethod.QR)
    view._payment_method_combo.setCurrentIndex(qr_index)
    _FakeQrPaymentDialog.result = QDialog.DialogCode.Accepted
    monkeypatch.setattr(sale_view_module, "QrPaymentDialog", _FakeQrPaymentDialog)

    view._on_complete_clicked()

    assert _FakeQrPaymentDialog.last_total == Decimal("20000")
    view._view_model.add_payment.assert_called_once_with(
        PaymentMethod.QR, Decimal("20000"), reference="REF-TEST"
    )


def test_complete_clicked_completes_directly_for_cash(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_cart_changed(_preview_with_total(Decimal("20000")))
    cash_index = view._payment_method_combo.findData(PaymentMethod.CASH)
    view._payment_method_combo.setCurrentIndex(cash_index)

    view._on_complete_clicked()

    view._view_model.complete_sale.assert_called_once()
