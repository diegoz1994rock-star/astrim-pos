"""Pruebas de UI de `MovementDialog` con `pytest-qt` (backend `offscreen`):
sin selector de dirección para Ajuste (ahora corrige a un valor absoluto),
y producto fijo (bodega siempre editable) cuando viene un producto
preseleccionado de la tabla de Existencias (una fila por producto)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pytestqt.qtbot import QtBot

from pos.modules.inventory.application.dto import WarehouseDTO
from pos.modules.inventory.presentation import movement_dialog as movement_dialog_module
from pos.modules.inventory.presentation.movement_dialog import MovementDialog, MovementMode
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType

_PRODUCT = ProductDTO(
    id=1,
    sku="VAR-12",
    name="Varilla 1/2",
    description=None,
    category_id=None,
    category_name=None,
    product_type=ProductType.SIMPLE,
    unit_price=Decimal("5"),
    cost_price=Decimal("3"),
    unit_of_measure="unidad",
    is_active=True,
    track_inventory=True,
)
_PRODUCTS = [_PRODUCT]
_WAREHOUSES = [WarehouseDTO(id=1, name="Bodega Principal", location=None, is_active=True)]


def test_adjustment_dialog_has_no_direction_selector(qtbot: QtBot) -> None:
    dialog = MovementDialog(MovementMode.ADJUSTMENT, _PRODUCTS, _WAREHOUSES)
    qtbot.addWidget(dialog)

    assert not hasattr(dialog, "_direction_combo")


def test_adjustment_computes_absolute_value(qtbot: QtBot) -> None:
    dialog = MovementDialog(MovementMode.ADJUSTMENT, _PRODUCTS, _WAREHOUSES, _PRODUCT)
    qtbot.addWidget(dialog)

    dialog._quantity_edit.setText("45")
    dialog._on_accept()

    values = dialog.values()
    assert values["quantity"] == Decimal("45")
    assert values["product_id"] == 1
    assert values["warehouse_id"] == 1


def test_adjustment_rejects_negative_quantity(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    # `_on_accept` muestra un `QMessageBox.warning` bloqueante ante un valor
    # inválido — se reemplaza por un no-op para no colgar la prueba
    # esperando un clic que nunca llega.
    monkeypatch.setattr(movement_dialog_module.QMessageBox, "warning", lambda *a, **k: None)
    dialog = MovementDialog(MovementMode.ADJUSTMENT, _PRODUCTS, _WAREHOUSES, _PRODUCT)
    qtbot.addWidget(dialog)

    dialog._quantity_edit.setText("-5")
    dialog._on_accept()

    assert dialog.result() == 0


def test_entry_rejects_zero_quantity(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(movement_dialog_module.QMessageBox, "warning", lambda *a, **k: None)
    dialog = MovementDialog(MovementMode.ENTRY, _PRODUCTS, _WAREHOUSES)
    qtbot.addWidget(dialog)

    dialog._quantity_edit.setText("0")
    dialog._on_accept()

    assert dialog.result() == 0


def test_preselected_product_fixes_product_but_warehouse_stays_editable(qtbot: QtBot) -> None:
    dialog = MovementDialog(MovementMode.ENTRY, _PRODUCTS, _WAREHOUSES, _PRODUCT)
    qtbot.addWidget(dialog)

    assert dialog._product_combo is None
    assert dialog._warehouse_combo is not None

    dialog._quantity_edit.setText("10")
    dialog._on_accept()

    values = dialog.values()
    assert values["product_id"] == 1
    assert values["warehouse_id"] == 1


def test_without_preselection_shows_editable_combos(qtbot: QtBot) -> None:
    dialog = MovementDialog(MovementMode.ENTRY, _PRODUCTS, _WAREHOUSES)
    qtbot.addWidget(dialog)

    assert dialog._product_combo is not None
    assert dialog._warehouse_combo is not None
