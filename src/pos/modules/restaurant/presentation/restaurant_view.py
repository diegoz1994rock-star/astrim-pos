"""Panel "Vendedor": toma de pedidos genérica para cualquier tipo de
negocio (mesero, vendedor, cajero, auxiliar, personal de mostrador o de
atención) — buscar productos por código/nombre/categoría, armar el
pedido y enviarlo a Despacho. Sin mesas, comensales ni reservas: el
pedido queda sin bodega/mesa asignada (ver `RestaurantService.create_order`,
`table_session_id=None`).

La búsqueda es 100% operable por teclado, estilo POS comercial: escribir
→ ↑/↓ recorren los resultados → Enter selecciona y pasa a Cantidad →
Enter agrega al pedido y vuelve al buscador — sin soltar el teclado. El
mouse sigue funcionando igual (clic en una fila, clic en los botones)
como camino alternativo."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.products.application.dto import CategoryDTO, ProductDTO
from pos.modules.products.domain.enums import SaleUnit
from pos.modules.restaurant.presentation.restaurant_view_model import RestaurantViewModel
from pos.modules.sales.application.dto import SalePreviewDTO
from pos.modules.sales.presentation.cart_item_edit_dialog import CartItemEditDialog
from pos.modules.scales.presentation.scale_weight_dialog import ScaleWeightDialog
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_table_to_contents, make_image_cell
from pos.shared_ui.widgets.toast import show_toast

_PRODUCT_COLUMNS = ["SKU", "Nombre", "Categoría", "Precio", "Existencia"]
_CART_COLUMNS = ["Imagen", "Producto", "Cantidad", "Notas", "Subtotal"]
_ALL_CATEGORIES_LABEL = "(todas las categorías)"

_PRODUCT_ROW_HEIGHT = 40
_CART_IMAGE_SIZE = 64
_CART_ROW_HEIGHT = 84
_SELECTED_PREVIEW_SIZE = 200
_CENTER = Qt.AlignmentFlag.AlignCenter


class RestaurantView(QWidget):
    def __init__(self, view_model: RestaurantViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._products: list[ProductDTO] = []
        self._categories: list[CategoryDTO] = []
        self._filtered_products: list[ProductDTO] = []
        self._current_preview: SalePreviewDTO | None = None
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area, layout = build_scrollable_page(self)
        outer_layout.addWidget(scroll_area)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)

        toolbar = QHBoxLayout()
        toolbar.addWidget(make_section_title("Vendedor"))
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._customer_name_edit = QLineEdit(self)
        self._customer_name_edit.setPlaceholderText(
            "Nombre del cliente (opcional — Consumidor Final si se deja vacío)"
        )
        layout.addWidget(self._customer_name_edit)

        self._customer_document_edit = QLineEdit(self)
        self._customer_document_edit.setPlaceholderText("Documento del cliente (opcional)")
        layout.addWidget(self._customer_document_edit)

        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText(
            "Escribí para buscar por nombre, SKU o código de barras…"
        )
        self._category_combo = QComboBox(self)
        search_row.addWidget(self._search_edit, stretch=2)
        search_row.addWidget(self._category_combo, stretch=1)
        layout.addLayout(search_row)

        self._product_table = QTableWidget(0, len(_PRODUCT_COLUMNS), self)
        self._product_table.setHorizontalHeaderLabels(_PRODUCT_COLUMNS)
        self._product_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._product_table.verticalHeader().setDefaultSectionSize(_PRODUCT_ROW_HEIGHT)
        self._product_table.setVisible(False)
        layout.addWidget(self._product_table)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(16)
        self._image_preview_container = QVBoxLayout()
        self._image_preview = make_image_cell(None, _SELECTED_PREVIEW_SIZE, 36)
        self._image_preview.setFixedSize(_SELECTED_PREVIEW_SIZE, _SELECTED_PREVIEW_SIZE)
        self._image_caption = QLabel("")
        self._image_caption.setAlignment(_CENTER)
        self._image_preview_container.addWidget(self._image_preview, alignment=_CENTER)
        self._image_preview_container.addWidget(self._image_caption)
        preview_row.addLayout(self._image_preview_container)

        details_layout = QVBoxLayout()
        details_layout.setSpacing(10)
        self._selected_product_label = QLabel("Selecciona un producto")
        self._selected_product_label.setAlignment(_CENTER)
        self._selected_product_label.setProperty("emphasis", True)
        details_layout.addWidget(self._selected_product_label)
        self._quantity_edit = QLineEdit(self)
        self._quantity_edit.setText("1")
        self._quantity_edit.setPlaceholderText("Cantidad")
        self._quantity_edit.setAlignment(_CENTER)
        self._notes_edit = QLineEdit(self)
        self._notes_edit.setPlaceholderText("Observación (opcional)")
        self._notes_edit.setAlignment(_CENTER)
        details_layout.addWidget(self._quantity_edit)
        details_layout.addWidget(self._notes_edit)
        self._add_to_order_button = QPushButton("Agregar al pedido")
        self._add_to_order_button.setMinimumHeight(36)
        details_layout.addWidget(self._add_to_order_button)
        preview_row.addLayout(details_layout, stretch=1)
        layout.addLayout(preview_row)

        cart_title = QLabel("Pedido en curso:")
        layout.addWidget(cart_title)
        self._cart_table = QTableWidget(0, len(_CART_COLUMNS), self)
        self._cart_table.setHorizontalHeaderLabels(_CART_COLUMNS)
        self._cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._cart_table.verticalHeader().setDefaultSectionSize(_CART_ROW_HEIGHT)
        layout.addWidget(self._cart_table)

        cart_actions = QHBoxLayout()
        cart_actions.setSpacing(12)
        self._edit_cart_item_button = QPushButton("Editar cantidad/nota")
        self._remove_cart_item_button = QPushButton("Quitar del pedido")
        for button in (self._edit_cart_item_button, self._remove_cart_item_button):
            button.setMinimumHeight(36)
            cart_actions.addWidget(button, stretch=1)
        layout.addLayout(cart_actions)

        self._totals_label = QLabel("Total: 0.00")
        self._totals_label.setAlignment(_CENTER)
        self._totals_label.setProperty("emphasis", True)
        layout.addWidget(self._totals_label)

        self._confirm_order_button = QPushButton("Confirmar pedido")
        self._confirm_order_button.setMinimumHeight(44)
        layout.addWidget(self._confirm_order_button)
        layout.addStretch()

    def _connect_signals(self) -> None:
        self._search_edit.textChanged.connect(self._apply_filters)
        self._search_edit.returnPressed.connect(self._on_search_enter_pressed)
        self._search_edit.installEventFilter(self)
        self._category_combo.currentIndexChanged.connect(self._apply_filters)
        self._product_table.itemSelectionChanged.connect(self._on_product_selection_changed)
        self._add_to_order_button.clicked.connect(self._on_add_to_order_clicked)
        self._quantity_edit.returnPressed.connect(self._on_quantity_enter_pressed)
        self._edit_cart_item_button.clicked.connect(self._on_edit_cart_item_clicked)
        self._remove_cart_item_button.clicked.connect(self._on_remove_cart_item_clicked)
        self._confirm_order_button.clicked.connect(self._on_confirm_order_clicked)

        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.categories_loaded.connect(self._on_categories_loaded)
        self._view_model.cart_changed.connect(self._on_cart_changed)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def eventFilter(self, watched: object, event: object) -> bool:
        if (
            watched is self._search_edit
            and isinstance(event, QEvent)
            and event.type() == QEvent.Type.KeyPress
        ):
            key = event.key()  # type: ignore[attr-defined]
            if key == Qt.Key.Key_Down:
                self._move_result_selection(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move_result_selection(-1)
                return True
        return super().eventFilter(watched, event)

    def _move_result_selection(self, delta: int) -> None:
        if not self._product_table.isVisible():
            return
        row_count = self._product_table.rowCount()
        if row_count == 0:
            return
        current = self._product_table.currentRow()
        new_row = 0 if current < 0 else min(max(current + delta, 0), row_count - 1)
        self._product_table.selectRow(new_row)

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products
        self._apply_filters()

    def _on_categories_loaded(self, categories: list[CategoryDTO]) -> None:
        self._categories = categories
        self._category_combo.clear()
        self._category_combo.addItem(_ALL_CATEGORIES_LABEL, userData=None)
        for category in categories:
            self._category_combo.addItem(category.name, userData=category.id)

    def _apply_filters(self) -> None:
        text = self._search_edit.text().strip().lower()
        if not text:
            self._filtered_products = []
            self._product_table.setRowCount(0)
            self._product_table.setVisible(False)
            return

        category_id = self._category_combo.currentData()
        filtered = [
            p
            for p in self._products
            if (text in p.sku.lower() or text in p.name.lower())
            and (category_id is None or p.category_id == category_id)
        ]
        self._filtered_products = filtered
        self._product_table.setRowCount(len(filtered))
        for row, product in enumerate(filtered):
            available = self._view_model.get_available_quantity(product.id)
            values = [
                product.sku,
                product.name,
                product.category_name or "",
                format_currency(product.unit_price),
                str(available) if product.track_inventory else "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(_CENTER)
                self._product_table.setItem(row, col, item)
        fit_table_to_contents(self._product_table)
        self._product_table.setVisible(bool(filtered))
        if filtered:
            self._product_table.selectRow(0)

    def _product_by_id(self, product_id: int) -> ProductDTO | None:
        return next((p for p in self._products if p.id == product_id), None)

    def _selected_product(self) -> ProductDTO | None:
        if not self._product_table.isVisible():
            return None
        rows = self._product_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._filtered_products[rows[0].row()]

    def _on_product_selection_changed(self) -> None:
        product = self._selected_product()
        if product is None:
            self._selected_product_label.setText("Selecciona un producto")
            self._image_caption.setText("")
            self._update_preview_image(None)
            return
        self._selected_product_label.setText(f"{product.name} — {format_currency(product.unit_price)}")
        self._update_preview_image(product.image_path)
        self._image_caption.setText("" if product.image_path else "Imagen no disponible")

    def _update_preview_image(self, image_path: str | None) -> None:
        new_label = make_image_cell(image_path, _SELECTED_PREVIEW_SIZE, 48)
        new_label.setFixedSize(_SELECTED_PREVIEW_SIZE, _SELECTED_PREVIEW_SIZE)
        self._image_preview_container.replaceWidget(self._image_preview, new_label)
        self._image_preview.deleteLater()
        self._image_preview = new_label

    def _on_search_enter_pressed(self) -> None:
        """Enter en el buscador: si hay un resultado seleccionado (flechas
        o el primero por defecto), pasa el foco a Cantidad — el mouse
        nunca hace falta. Para productos por peso, abre la lectura de
        báscula en su lugar (ver `ScaleWeightDialog`)."""
        product = self._selected_product()
        if not self._product_table.isVisible() or product is None:
            return
        if product.sale_unit is SaleUnit.WEIGHT:
            self._open_scale_weight_dialog(product)
            return
        self._quantity_edit.setFocus()
        self._quantity_edit.selectAll()

    def _open_scale_weight_dialog(self, product: ProductDTO) -> None:
        dialog = ScaleWeightDialog(
            product_name=product.name,
            unit_price=product.unit_price,
            unit_of_measure=product.unit_of_measure,
            scale_read_service=self._view_model.scale_read_service,
            min_weight=product.min_weight,
            max_weight=product.max_weight,
            parent=self,
        )
        if dialog.exec() != ScaleWeightDialog.DialogCode.Accepted:
            return
        self._view_model.add_item(
            product.id, dialog.weight(), self._notes_edit.text().strip() or None
        )
        self._notes_edit.clear()
        self._search_edit.clear()
        self._search_edit.setFocus()

    def _on_quantity_enter_pressed(self) -> None:
        """Enter en Cantidad: agrega al pedido (misma acción que el botón)
        y vuelve al buscador limpio para el siguiente producto."""
        if self._on_add_to_order_clicked():
            self._quantity_edit.setText("1")
            self._search_edit.clear()
            self._search_edit.setFocus()

    def _on_add_to_order_clicked(self) -> bool:
        product = self._selected_product()
        if product is None:
            self._show_error("Selecciona un producto.")
            return False
        try:
            quantity = Decimal(self._quantity_edit.text())
        except InvalidOperation:
            self._show_error("La cantidad debe ser un número válido.")
            return False
        self._view_model.add_item(product.id, quantity, self._notes_edit.text().strip() or None)
        self._notes_edit.clear()
        return True

    def _selected_cart_row(self) -> int | None:
        rows = self._cart_table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _on_cart_changed(self, preview: SalePreviewDTO) -> None:
        self._current_preview = preview
        self._cart_table.setRowCount(len(preview.items))
        for row, line in enumerate(preview.items):
            product = self._product_by_id(line.product_id)
            image_path = product.image_path if product is not None else None
            self._cart_table.setCellWidget(
                row, 0, make_image_cell(image_path, _CART_IMAGE_SIZE, 20)
            )
            values = [
                line.product_name,
                str(line.quantity),
                line.note or "",
                format_currency(line.line_total),
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setTextAlignment(_CENTER)
                self._cart_table.setItem(row, col, item)
        fit_table_to_contents(self._cart_table)
        self._totals_label.setText(
            f"Subtotal: {format_currency(preview.subtotal)}  "
            f"Descuento: {format_currency(preview.discount_total)}  "
            f"Impuesto: {format_currency(preview.tax_total)}  "
            f"Total: {format_currency(preview.total)}"
        )

    def _on_edit_cart_item_clicked(self) -> None:
        row = self._selected_cart_row()
        if row is None or self._current_preview is None:
            self._show_error("Selecciona un producto del pedido.")
            return
        line = self._current_preview.items[row]
        dialog = CartItemEditDialog(line.product_name, line.quantity, line.note, parent=self)
        if dialog.exec() != CartItemEditDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.update_item(row, quantity=values["quantity"], note=values["note"])

    def _on_remove_cart_item_clicked(self) -> None:
        row = self._selected_cart_row()
        if row is None:
            self._show_error("Selecciona un producto del pedido.")
            return
        self._view_model.remove_item(row)

    def _on_confirm_order_clicked(self) -> None:
        if self._view_model.confirm_order(
            self._customer_name_edit.text().strip() or None,
            self._customer_document_edit.text().strip() or None,
        ):
            self._customer_name_edit.clear()
            self._customer_document_edit.clear()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
