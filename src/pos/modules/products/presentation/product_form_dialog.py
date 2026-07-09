"""Diálogo de creación de producto."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QWidget,
)

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.products.application.dto import CategoryDTO
from pos.modules.products.domain.enums import ProductType


class ProductFormDialog(QDialog):
    """Formulario modal para crear un producto nuevo."""

    def __init__(
        self,
        categories: list[CategoryDTO],
        tax_names: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo producto")
        self._categories = categories

        self._sku_edit = QLineEdit(self)
        self._name_edit = QLineEdit(self)
        self._description_edit = QLineEdit(self)
        self._unit_price_edit = QLineEdit(self)
        self._cost_price_edit = QLineEdit(self)
        self._unit_of_measure_edit = QLineEdit(self)
        self._unit_of_measure_edit.setText("unidad")

        self._category_combo = QComboBox(self)
        self._category_combo.addItem("(ninguna)", userData=None)
        for category in categories:
            self._category_combo.addItem(category.name, userData=category.id)

        self._type_combo = QComboBox(self)
        for product_type in ProductType:
            self._type_combo.addItem(product_type.value, userData=product_type)

        self._track_inventory_check = QCheckBox("Controlar inventario", self)
        self._track_inventory_check.setChecked(True)

        self._taxes_list = QListWidget(self)
        for tax_name in tax_names:
            item = QListWidgetItem(tax_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._taxes_list.addItem(item)

        form = QFormLayout(self)
        form.addRow("SKU", self._sku_edit)
        form.addRow("Nombre", self._name_edit)
        form.addRow("Descripción (opcional)", self._description_edit)
        form.addRow("Categoría", self._category_combo)
        form.addRow("Tipo", self._type_combo)
        form.addRow("Precio de venta", self._unit_price_edit)
        form.addRow("Costo", self._cost_price_edit)
        form.addRow("Unidad de medida", self._unit_of_measure_edit)
        form.addRow(self._track_inventory_check)
        form.addRow("Impuestos", self._taxes_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._values: dict[str, object] | None = None

    def _on_accept(self) -> None:
        try:
            unit_price = Decimal(self._unit_price_edit.text() or "0")
            cost_price = Decimal(self._cost_price_edit.text() or "0")
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "Los precios deben ser números válidos.")
            return
        if unit_price < 0 or cost_price < 0:
            QMessageBox.warning(self, "Error", str(BusinessRuleViolationError("Precios negativos")))
            return

        selected_taxes = {
            self._taxes_list.item(i).text()
            for i in range(self._taxes_list.count())
            if self._taxes_list.item(i).checkState() == Qt.CheckState.Checked
        }

        self._values = {
            "sku": self._sku_edit.text().strip(),
            "name": self._name_edit.text().strip(),
            "description": self._description_edit.text().strip() or None,
            "category_id": self._category_combo.currentData(),
            "product_type": self._type_combo.currentData(),
            "unit_price": unit_price,
            "cost_price": cost_price,
            "unit_of_measure": self._unit_of_measure_edit.text().strip() or "unidad",
            "track_inventory": self._track_inventory_check.isChecked(),
            "tax_codes": selected_taxes,
        }
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
