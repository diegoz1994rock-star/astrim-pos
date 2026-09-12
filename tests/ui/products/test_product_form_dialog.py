"""Pruebas de UI de `ProductFormDialog` con `pytest-qt` (backend `offscreen`):
el modo edición precarga los datos y un error de validación no debe cerrar
el diálogo ni perder lo ya ingresado — mismo patrón que `UserFormDialog`."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from pos.core.exceptions import ConflictError
from pos.modules.products.application.dto import CategoryDTO, ProductDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.presentation.product_form_dialog import ProductFormDialog

_CATEGORIES = [CategoryDTO(id=1, name="Bebidas", is_active=True)]


def _existing_product() -> ProductDTO:
    return ProductDTO(
        id=42,
        sku="SKU-42",
        name="Gaseosa",
        description="Bebida gaseosa",
        category_id=1,
        category_name="Bebidas",
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("5.50"),
        cost_price=Decimal("2.00"),
        unit_of_measure="unidad",
        is_active=True,
        track_inventory=True,
    )


def test_create_mode_has_no_prefill_and_calls_create_product(qtbot: QtBot, monkeypatch) -> None:
    # Sin código de barras, `_on_accept_clicked` pregunta con un
    # `QMessageBox.question` real (modal) si continuar sin código — se
    # mockea para no bloquear la prueba (bug preexistente y ajeno a esta
    # entrega: nunca se mockeaba, mismo patrón que ya usa `test_sale_view.py`).
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.StandardButton.Yes))
    fake_view_model = Mock()
    dialog = ProductFormDialog(_CATEGORIES, fake_view_model)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Nuevo producto"
    assert dialog._sku_edit.text() == ""

    dialog._sku_edit.setText("SKU-1")
    dialog._name_edit.setText("Producto Nuevo")
    dialog._unit_price_edit.setText("10")
    dialog._cost_price_edit.setText("5")

    dialog._on_accept_clicked()

    fake_view_model.create_product.assert_called_once()
    fake_view_model.update_product.assert_not_called()
    assert dialog.result() == 1


def test_edit_mode_prefills_fields_and_calls_update_product(qtbot: QtBot, monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.StandardButton.Yes))
    fake_view_model = Mock()
    fake_view_model.product_service.list_barcodes.return_value = []
    product = _existing_product()
    dialog = ProductFormDialog(_CATEGORIES, fake_view_model, existing_product=product)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Editar producto"
    assert dialog._sku_edit.text() == "SKU-42"
    assert dialog._name_edit.text() == "Gaseosa"
    assert dialog._description_edit.toPlainText() == "Bebida gaseosa"
    assert dialog._unit_price_edit.text() == "5.50"
    assert dialog._category_combo.currentData() == 1

    dialog._name_edit.setText("Gaseosa Grande")
    dialog._on_accept_clicked()

    fake_view_model.update_product.assert_called_once()
    args, kwargs = fake_view_model.update_product.call_args
    assert args[0] == 42
    assert kwargs["name"] == "Gaseosa Grande"
    fake_view_model.create_product.assert_not_called()
    assert dialog.result() == 1


def test_client_side_price_error_keeps_dialog_open_and_data_intact(qtbot: QtBot) -> None:
    fake_view_model = Mock()
    dialog = ProductFormDialog(_CATEGORIES, fake_view_model)
    qtbot.addWidget(dialog)

    dialog._sku_edit.setText("SKU-1")
    dialog._name_edit.setText("Producto Nuevo")
    dialog._unit_price_edit.setText("no-es-un-numero")

    dialog._on_accept_clicked()

    fake_view_model.create_product.assert_not_called()
    assert dialog.result() == 0
    assert dialog._price_error.text() == "Los precios deben ser números válidos."
    assert dialog._sku_edit.text() == "SKU-1"
    assert dialog._name_edit.text() == "Producto Nuevo"


def test_server_side_sku_conflict_is_routed_to_sku_field(qtbot: QtBot, monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.StandardButton.Yes))
    fake_view_model = Mock()
    fake_view_model.create_product.side_effect = ConflictError(
        "Ya existe un producto con el SKU 'SKU-1'."
    )
    dialog = ProductFormDialog(_CATEGORIES, fake_view_model)
    qtbot.addWidget(dialog)

    dialog._sku_edit.setText("SKU-1")
    dialog._name_edit.setText("Producto Nuevo")
    dialog._unit_price_edit.setText("10")
    dialog._cost_price_edit.setText("5")

    dialog._on_accept_clicked()

    assert dialog.result() == 0
    assert dialog._sku_error.text() == "Ya existe un producto con el SKU 'SKU-1'."
