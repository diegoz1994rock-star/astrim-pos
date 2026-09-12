"""Pantalla de administración de productos: tabla + alta + receta/combo."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from pos.modules.products.application.dto import CategoryDTO, ProductDTO
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.presentation.product_form_dialog import ProductFormDialog
from pos.modules.products.presentation.products_table_model import COLUMNS, ProductsTableModel
from pos.modules.products.presentation.products_view_model import ProductsViewModel
from pos.modules.products.presentation.recipe_combo_dialog import RecipeComboDialog
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.search_bar import SearchBar
from pos.shared_ui.widgets.search_filter_proxy_model import SearchFilterProxyModel
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import (
    ImageCellDelegate,
    StatusChipDelegate,
    fit_table_view_to_contents,
)
from pos.shared_ui.widgets.toast import show_toast

_ROW_HEIGHT = 92
_IMAGE_COLUMN_WIDTH = 110
"""Ancho fijo de la columna "Imagen" — nunca se recalcula automáticamente
(ver `setSectionResizeMode(..., Fixed)` en `_build_ui`), así la miniatura
siempre tiene el mismo espacio disponible sin importar cuántas columnas
haya ni el tamaño de la ventana. Coincide a propósito con
`setMinimumSectionSize(110)` (ya existente, aplica a todas las columnas
por igual — Qt no permite un mínimo por columna) para que no haya ningún
ajuste sorpresa entre el valor pedido y el mínimo global."""


class ProductsView(QWidget):
    def __init__(self, view_model: ProductsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._products: list[ProductDTO] = []
        self._categories: list[CategoryDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        toolbar = QHBoxLayout()
        title = make_section_title("Productos")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nuevo producto")
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._search_bar = SearchBar(
            "Buscar producto por nombre, código, SKU, código de barras o categoría...", self
        )
        layout.addWidget(self._search_bar)
        QShortcut(QKeySequence.StandardKey.Find, self).activated.connect(self._search_bar.focus)

        self._source_model = ProductsTableModel(self)
        self._proxy_model = SearchFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)

        self._table = QTableView(self)
        self._table.setModel(self._proxy_model)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setMinimumSectionSize(110)
        image_column = COLUMNS.index("Imagen")
        self._image_delegate = ImageCellDelegate(cell_size=_IMAGE_COLUMN_WIDTH, parent=self._table)
        self._table.setItemDelegateForColumn(image_column, self._image_delegate)
        self._table.horizontalHeader().setSectionResizeMode(
            image_column, QHeaderView.ResizeMode.Fixed
        )
        self._status_delegate = StatusChipDelegate(self._table)
        self._table.setItemDelegateForColumn(COLUMNS.index("Estado"), self._status_delegate)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_table_double_clicked)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._edit_button = QPushButton("Editar")
        self._delete_button = QPushButton("Eliminar producto")
        self._toggle_button = QPushButton("Activar/Desactivar seleccionado")
        for button in (self._edit_button, self._delete_button, self._toggle_button):
            actions.addWidget(button, stretch=1)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._search_bar.text_changed.connect(self._on_search_text_changed)
        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.categories_loaded.connect(self._on_categories_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_search_text_changed(self, text: str) -> None:
        self._proxy_model.set_search_text(text)
        fit_table_view_to_contents(self._table)

    def _on_categories_loaded(self, categories: list[CategoryDTO]) -> None:
        self._categories = categories

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products
        self._source_model.set_products(products)
        self._table.resizeColumnsToContents()
        self._table.setColumnWidth(COLUMNS.index("Imagen"), _IMAGE_COLUMN_WIDTH)
        fit_table_view_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = ProductFormDialog(self._categories, self._view_model, parent=self)
        dialog.exec()

    def _selected_product(self) -> ProductDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        source_row = self._proxy_model.mapToSource(selected_rows[0]).row()
        return self._source_model.product_at(source_row)

    def _on_table_double_clicked(self, index: QModelIndex) -> None:
        source_row = self._proxy_model.mapToSource(index).row()
        self._open_edit_dialog(self._source_model.product_at(source_row))

    def _on_edit_clicked(self) -> None:
        product = self._selected_product()
        if product is None:
            self._show_error("Selecciona un producto de la tabla.")
            return
        self._open_edit_dialog(product)

    def _open_edit_dialog(self, product: ProductDTO) -> None:
        dialog = ProductFormDialog(
            self._categories,
            self._view_model,
            existing_product=product,
            parent=self,
        )
        dialog.exec()

    def _on_toggle_clicked(self) -> None:
        product = self._selected_product()
        if product is None:
            self._show_error("Selecciona un producto de la tabla.")
            return
        self._view_model.set_active(product, not product.is_active)

    def _on_delete_clicked(self) -> None:
        product = self._selected_product()
        if product is None:
            self._show_error("Selecciona un producto de la tabla.")
            return
        confirmed = QMessageBox.question(
            self,
            "Eliminar producto",
            f"¿Seguro que deseas eliminar el producto '{product.name}'? "
            "Esta acción no se puede deshacer.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._view_model.delete_product(product.id)

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
        show_toast(self, message)
