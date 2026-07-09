"""Pantalla de administración de productos: tabla + alta + receta/combo."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.products.application.dto import CategoryDTO, ProductDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.presentation.product_form_dialog import ProductFormDialog
from pos.modules.products.presentation.products_view_model import ProductsViewModel
from pos.modules.products.presentation.recipe_combo_dialog import RecipeComboDialog

_COLUMNS = ["SKU", "Nombre", "Categoría", "Tipo", "Precio", "Estado"]


class ProductsView(QWidget):
    def __init__(self, view_model: ProductsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._products: list[ProductDTO] = []
        self._categories: list[CategoryDTO] = []
        self._tax_names: list[str] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Productos")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nuevo producto")
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._toggle_button = QPushButton("Activar/Desactivar seleccionado")
        self._recipe_combo_button = QPushButton("Gestionar receta/combo")
        actions.addWidget(self._toggle_button)
        actions.addWidget(self._recipe_combo_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._recipe_combo_button.clicked.connect(self._on_recipe_combo_clicked)
        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.categories_loaded.connect(self._on_categories_loaded)
        self._view_model.tax_names_loaded.connect(self._on_tax_names_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_categories_loaded(self, categories: list[CategoryDTO]) -> None:
        self._categories = categories

    def _on_tax_names_loaded(self, tax_names: list[str]) -> None:
        self._tax_names = tax_names

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products
        self._table.setRowCount(len(products))
        for row, product in enumerate(products):
            self._table.setItem(row, 0, QTableWidgetItem(product.sku))
            self._table.setItem(row, 1, QTableWidgetItem(product.name))
            self._table.setItem(row, 2, QTableWidgetItem(product.category_name or ""))
            self._table.setItem(row, 3, QTableWidgetItem(product.product_type.value))
            self._table.setItem(row, 4, QTableWidgetItem(f"{product.unit_price:.2f}"))
            self._table.setItem(
                row, 5, QTableWidgetItem("Activo" if product.is_active else "Inactivo")
            )

    def _on_new_clicked(self) -> None:
        dialog = ProductFormDialog(self._categories, self._tax_names, self)
        if dialog.exec() == ProductFormDialog.DialogCode.Accepted:
            self._view_model.create_product(**dialog.values())

    def _selected_product(self) -> ProductDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._products[selected_rows[0].row()]

    def _on_toggle_clicked(self) -> None:
        product = self._selected_product()
        if product is None:
            self._show_error("Selecciona un producto de la tabla.")
            return
        self._view_model.set_active(product, not product.is_active)

    def _on_recipe_combo_clicked(self) -> None:
        product = self._selected_product()
        if product is None:
            self._show_error("Selecciona un producto de la tabla.")
            return
        if product.product_type not in (ProductType.COMPOUND, ProductType.COMBO):
            self._show_error(
                "Solo los productos de tipo 'compound' (receta) o 'combo' admiten composición."
            )
            return
        candidates = [p for p in self._products if p.id != product.id]
        dialog = RecipeComboDialog(product, candidates, self._view_model, self)
        dialog.exec()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
