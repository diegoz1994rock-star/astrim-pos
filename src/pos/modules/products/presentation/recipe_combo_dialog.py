"""Diálogo para componer la receta de un producto compuesto o los ítems de
un combo, según el tipo del producto seleccionado."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.presentation.products_view_model import ProductsViewModel


class RecipeComboDialog(QDialog):
    """Agrega insumos (receta) o componentes (combo) al producto dado."""

    def __init__(
        self,
        product: ProductDTO,
        candidates: list[ProductDTO],
        view_model: ProductsViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._product = product
        self._view_model = view_model
        is_recipe = product.product_type is ProductType.COMPOUND
        self.setWindowTitle(
            f"{'Receta' if is_recipe else 'Combo'} de {product.name}"
        )

        self._candidate_combo = QComboBox(self)
        for candidate in candidates:
            self._candidate_combo.addItem(candidate.name, userData=candidate.id)

        self._quantity_edit = QLineEdit(self)
        self._quantity_edit.setText("1")

        self._unit_edit = QLineEdit(self)
        self._unit_edit.setText(product.unit_of_measure)
        self._unit_edit.setVisible(is_recipe)

        form = QFormLayout()
        form.addRow("Producto" if not is_recipe else "Insumo", self._candidate_combo)
        form.addRow("Cantidad", self._quantity_edit)
        if is_recipe:
            form.addRow("Unidad", self._unit_edit)

        add_button = QPushButton("Agregar")
        add_button.clicked.connect(self._on_add_clicked)

        self._items_list = QListWidget(self)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(add_button)
        layout.addWidget(QLabel("Contenido actual:"))
        layout.addWidget(self._items_list)

        close_row = QHBoxLayout()
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        close_row.addStretch()
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

        self._is_recipe = is_recipe
        self._refresh_items()

    def _refresh_items(self) -> None:
        self._items_list.clear()
        service = self._view_model.product_service
        if self._is_recipe:
            for recipe_item in service.list_recipe_items(self._product.id):
                self._items_list.addItem(
                    f"{recipe_item.ingredient_name} — "
                    f"{recipe_item.quantity} {recipe_item.unit_of_measure}"
                )
        else:
            for combo_item in service.list_combo_items(self._product.id):
                self._items_list.addItem(f"{combo_item.product_name} × {combo_item.quantity}")

    def _on_add_clicked(self) -> None:
        try:
            quantity = Decimal(self._quantity_edit.text())
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "La cantidad debe ser un número válido.")
            return

        candidate_id = self._candidate_combo.currentData()
        if candidate_id is None:
            QMessageBox.warning(self, "Error", "Selecciona un producto.")
            return

        if self._is_recipe:
            self._view_model.add_recipe_item(
                self._product.id, candidate_id, quantity, self._unit_edit.text().strip()
            )
        else:
            self._view_model.add_combo_item(self._product.id, candidate_id, quantity)

        self._refresh_items()
