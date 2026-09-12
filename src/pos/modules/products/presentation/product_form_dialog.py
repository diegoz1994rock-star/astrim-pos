"""Diálogo de creación/edición de producto."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.modules.products.application.dto import CategoryDTO, ProductBarcodeDTO, ProductDTO
from pos.modules.products.application.product_service import MAX_BARCODE_LENGTH
from pos.modules.products.domain.enums import ProductType, SaleUnit
from pos.modules.products.infrastructure.image_storage import save_product_image
from pos.modules.products.presentation.add_barcode_dialog import AddBarcodeDialog
from pos.modules.products.presentation.products_view_model import ProductsViewModel
from pos.shared_ui.widgets.table_utils import fit_list_to_contents

_BARCODE_CONFLICT_MESSAGE = "Este código ya está registrado para el producto {name}."
_BARCODE_TOO_LONG_MESSAGE = (
    f"El código de barras no puede tener más de {MAX_BARCODE_LENGTH} caracteres."
)

_BARCODE_ID_ROLE = Qt.ItemDataRole.UserRole


@dataclass
class _StagedBarcode:
    barcode_id: int | None
    """`None` = código nuevo, todavía no persistido."""
    code: str

_FIELD_MIN_WIDTH = 380
_DESCRIPTION_MIN_HEIGHT = 100
_IMAGE_PREVIEW_SIZE = 96
_IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.bmp)"
_SALE_UNIT_LABELS = {SaleUnit.UNIT: "Unidad", SaleUnit.WEIGHT: "Peso"}
_PRICE_ROW_LABELS = {SaleUnit.UNIT: "Precio unitario", SaleUnit.WEIGHT: "Precio por kilogramo"}
_UNIT_OF_MEASURE_BY_SALE_UNIT = {SaleUnit.UNIT: "unidad", SaleUnit.WEIGHT: "kg"}
"""El cajero/administrador nunca escribe la unidad de medida a mano — se
deriva del "Tipo de venta" elegido (ver `_on_accept_clicked`). La columna
`unit_of_measure` sigue existiendo en la base (compatibilidad con
`pdf_renderer`/`ScaleWeightDialog`, que la usan para mostrar "kg"), pero ya
no es un campo libre del formulario."""


def _error_label() -> QLabel:
    label = QLabel("")
    label.setProperty("role", "danger")
    label.setWordWrap(True)
    label.setVisible(False)
    return label


class ProductFormDialog(QDialog):
    """Formulario modal para crear un producto nuevo o editar uno
    existente (si se pasa `existing_product`).

    Los errores de validación se muestran junto al campo correspondiente
    sin cerrar el diálogo ni perder lo ya escrito — mismo patrón que
    `UserFormDialog`."""

    def __init__(
        self,
        categories: list[CategoryDTO],
        view_model: ProductsViewModel,
        existing_product: ProductDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._categories = categories
        self._view_model = view_model
        self._existing_product = existing_product
        self._image_path: str | None = (
            existing_product.image_path if existing_product is not None else None
        )
        self._original_barcodes: list[ProductBarcodeDTO] = []
        self._staged_barcodes: list[_StagedBarcode] = []
        self.setWindowTitle("Editar producto" if existing_product else "Nuevo producto")
        self.resize(680, 760)

        self._build_ui()
        if existing_product is not None:
            self._load_existing_product(existing_product)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)

        self._form_error = _error_label()
        root_layout.addWidget(self._form_error)
        root_layout.addWidget(self._build_image_section())

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        form = self._form = QFormLayout(content)

        self._sku_edit = QLineEdit(self)
        self._sku_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._sku_error = _error_label()
        self._name_edit = QLineEdit(self)
        self._name_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._name_error = _error_label()
        self._description_edit = QTextEdit(self)
        self._description_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._description_edit.setMinimumHeight(_DESCRIPTION_MIN_HEIGHT)

        self._category_combo = QComboBox(self)
        self._category_combo.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._category_combo.addItem("(ninguna)", userData=None)
        for category in self._categories:
            self._category_combo.addItem(category.name, userData=category.id)

        self._type_combo = QComboBox(self)
        self._type_combo.setMinimumWidth(_FIELD_MIN_WIDTH)
        for product_type in ProductType:
            self._type_combo.addItem(product_type.value, userData=product_type)

        self._unit_price_edit = QLineEdit(self)
        self._unit_price_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._price_error = _error_label()
        self._cost_price_edit = QLineEdit(self)
        self._cost_price_edit.setMinimumWidth(_FIELD_MIN_WIDTH)

        # Obligatorio: siempre hay una opción preseleccionada (Unidad), el
        # combo nunca queda vacío — no hace falta validación adicional.
        self._sale_unit_combo = QComboBox(self)
        self._sale_unit_combo.setMinimumWidth(_FIELD_MIN_WIDTH)
        for sale_unit, label in _SALE_UNIT_LABELS.items():
            self._sale_unit_combo.addItem(label, userData=sale_unit)
        self._sale_unit_combo.currentIndexChanged.connect(self._update_weight_fields_visibility)
        self._sale_unit_combo.currentIndexChanged.connect(self._update_price_label)

        self._min_weight_edit = QLineEdit(self)
        self._min_weight_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._min_weight_edit.setPlaceholderText("Ej. 0.100 (opcional)")
        self._max_weight_edit = QLineEdit(self)
        self._max_weight_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._max_weight_edit.setPlaceholderText("Ej. 10.000 (opcional)")
        self._weight_decimal_places_edit = QLineEdit(self)
        self._weight_decimal_places_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._weight_decimal_places_edit.setPlaceholderText(
            "Vacío = usar los decimales configurados en la báscula"
        )
        self._weight_error = _error_label()

        self._track_inventory_check = QCheckBox("Controlar inventario", self)
        self._track_inventory_check.setChecked(True)

        form.addRow("SKU", self._sku_edit)
        form.addRow("", self._sku_error)
        form.addRow("Nombre", self._name_edit)
        form.addRow("", self._name_error)
        form.addRow("Descripción", self._description_edit)
        form.addRow("Categoría", self._category_combo)
        form.addRow("Tipo", self._type_combo)
        form.addRow("Precio de venta", self._unit_price_edit)
        form.addRow("", self._price_error)
        form.addRow("Costo", self._cost_price_edit)
        form.addRow("Tipo de venta", self._sale_unit_combo)
        form.addRow("Peso mínimo", self._min_weight_edit)
        form.addRow("Peso máximo", self._max_weight_edit)
        form.addRow("Decimales de peso", self._weight_decimal_places_edit)
        form.addRow("", self._weight_error)
        form.addRow(self._track_inventory_check)
        form.addRow(self._build_barcode_section())
        self._update_weight_fields_visibility()
        self._update_price_label()

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept_clicked)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _update_weight_fields_visibility(self) -> None:
        """Peso mínimo/máximo/decimales solo aplican a productos por peso
        — nunca se muestran como opción decorativa en un producto por
        unidad, donde no tienen ningún efecto."""
        is_weight = self._sale_unit_combo.currentData() is SaleUnit.WEIGHT
        for widget in (
            self._min_weight_edit, self._max_weight_edit, self._weight_decimal_places_edit,
        ):
            self._set_row_visible(widget, is_weight)
        if not is_weight:
            self._weight_error.setVisible(False)

    def _update_price_label(self) -> None:
        """"Precio unitario" o "Precio por kilogramo" según el "Tipo de
        venta" elegido — el mismo campo `_unit_price_edit`, solo cambia el
        rótulo, para que nunca quede ambiguo qué representa el número."""
        sale_unit = self._sale_unit_combo.currentData()
        label = self._form.labelForField(self._unit_price_edit)
        if label is not None:
            label.setText(_PRICE_ROW_LABELS.get(sale_unit, "Precio de venta"))

    def _build_image_section(self) -> QWidget:
        self._image_preview = QLabel(self)
        self._image_preview.setFixedSize(_IMAGE_PREVIEW_SIZE, _IMAGE_PREVIEW_SIZE)
        self._image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_preview.setText("Sin imagen")
        self._image_button = QPushButton("Seleccionar imagen", self)
        self._image_button.clicked.connect(self._on_select_image_clicked)

        row = QHBoxLayout()
        row.addWidget(self._image_preview)
        row.addWidget(self._image_button)
        row.addStretch()
        container = QWidget(self)
        container.setLayout(row)
        return container

    def _set_image_preview(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            _IMAGE_PREVIEW_SIZE,
            _IMAGE_PREVIEW_SIZE,
            aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
            mode=Qt.TransformationMode.SmoothTransformation,
        )
        self._image_preview.setText("")
        self._image_preview.setPixmap(scaled)

    def _on_select_image_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", _IMAGE_FILTER)
        if not path:
            return
        self._image_path = save_product_image(Path(path))
        self._set_image_preview(self._image_path)

    def _build_barcode_section(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Código de barras"))

        self._barcode_edit = QLineEdit(self)
        self._barcode_edit.setMinimumWidth(_FIELD_MIN_WIDTH)
        self._barcode_edit.setPlaceholderText("Escríbelo, escanéalo o genera uno automático")
        self._barcode_edit.returnPressed.connect(self._on_barcode_field_entered)
        layout.addWidget(self._barcode_edit)
        self._barcode_error = _error_label()
        layout.addWidget(self._barcode_error)

        primary_buttons_row = QHBoxLayout()
        self._generate_barcode_button = QPushButton("Generar código automáticamente", self)
        self._generate_barcode_button.clicked.connect(self._on_generate_barcode_clicked)
        self._scan_barcode_button = QPushButton("Escanear código", self)
        self._scan_barcode_button.clicked.connect(self._on_scan_barcode_clicked)
        primary_buttons_row.addWidget(self._generate_barcode_button)
        primary_buttons_row.addWidget(self._scan_barcode_button)
        layout.addLayout(primary_buttons_row)

        layout.addWidget(QLabel("Códigos adicionales (otras presentaciones del mismo producto)"))
        self._barcode_list = QListWidget(self)
        self._barcode_list.itemDoubleClicked.connect(self._on_barcode_double_clicked)
        layout.addWidget(self._barcode_list)

        buttons_row = QHBoxLayout()
        self._add_barcode_button = QPushButton("Agregar código adicional", self)
        self._add_barcode_button.clicked.connect(self._on_add_barcode_clicked)
        self._remove_barcode_button = QPushButton("Eliminar seleccionado", self)
        self._remove_barcode_button.clicked.connect(self._on_remove_barcode_clicked)
        buttons_row.addWidget(self._add_barcode_button)
        buttons_row.addWidget(self._remove_barcode_button)
        layout.addLayout(buttons_row)

        self._render_barcode_list()
        return container

    def _additional_barcodes(self) -> list[_StagedBarcode]:
        """Todo lo que no sea el código principal (índice 0 de
        `_staged_barcodes`, mostrado directo en `_barcode_edit`)."""
        return self._staged_barcodes[1:]

    def _render_barcode_list(self) -> None:
        self._barcode_list.clear()
        for entry in self._additional_barcodes():
            item = QListWidgetItem(entry.code)
            item.setData(_BARCODE_ID_ROLE, entry)
            self._barcode_list.addItem(item)
        fit_list_to_contents(self._barcode_list)

    def _on_barcode_field_entered(self) -> None:
        """Enter en el campo principal (real o disparado por un lector
        HID) no debe cerrar ni guardar el formulario — solo valida en el
        momento y muestra el error ahí mismo si el código ya pertenece a
        otro producto, sin bloquear el resto del formulario."""
        code = self._barcode_edit.text().strip()
        self._barcode_error.setVisible(False)
        if not code:
            return
        if len(code) > MAX_BARCODE_LENGTH:
            self._set_field_error(self._barcode_error, _BARCODE_TOO_LONG_MESSAGE)
            return
        exclude_id = self._staged_barcodes[0].barcode_id if self._staged_barcodes else None
        conflict = self._view_model.product_service.find_barcode_conflict(
            code, exclude_barcode_id=exclude_id
        )
        if conflict is not None:
            self._set_field_error(
                self._barcode_error, _BARCODE_CONFLICT_MESSAGE.format(name=conflict.name)
            )

    def _on_generate_barcode_clicked(self) -> None:
        code = self._view_model.product_service.generate_unique_barcode()
        self._barcode_edit.setText(code)
        self._barcode_error.setVisible(False)

    def _on_scan_barcode_clicked(self) -> None:
        """El lector HID escribe directo donde esté el foco — este botón
        solo prepara el campo (lo limpia y le da foco); no hace falta
        ningún modo especial ni presionar Enter a mano."""
        self._barcode_edit.clear()
        self._barcode_error.setVisible(False)
        self._barcode_edit.setFocus()

    def _on_add_barcode_clicked(self) -> None:
        existing_codes = {entry.code for entry in self._staged_barcodes}
        dialog = AddBarcodeDialog(self._view_model.product_service, existing_codes, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._staged_barcodes.append(_StagedBarcode(barcode_id=None, code=dialog.code()))
        self._render_barcode_list()

    def _on_remove_barcode_clicked(self) -> None:
        row = self._barcode_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Selecciona un código de la lista.")
            return
        # +1: el índice 0 de `_staged_barcodes` es el código principal,
        # nunca mostrado en esta lista (ver `_additional_barcodes`).
        del self._staged_barcodes[row + 1]
        self._render_barcode_list()

    def _on_barcode_double_clicked(self, item: QListWidgetItem) -> None:
        entry: _StagedBarcode = item.data(_BARCODE_ID_ROLE)
        existing_codes = {b.code for b in self._staged_barcodes if b is not entry}
        dialog = AddBarcodeDialog(
            self._view_model.product_service,
            existing_codes,
            exclude_barcode_id=entry.barcode_id,
            initial_code=entry.code,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entry.code = dialog.code()
        self._render_barcode_list()

    def _apply_staged_barcodes(self, product_id: int) -> None:
        service = self._view_model.product_service
        original_by_id = {b.id: b.code for b in self._original_barcodes}
        staged_ids = {b.barcode_id for b in self._staged_barcodes if b.barcode_id is not None}
        for removed_id in set(original_by_id) - staged_ids:
            service.remove_barcode(removed_id)
        for entry in self._staged_barcodes:
            if entry.barcode_id is None:
                service.add_barcode(product_id, entry.code)
            elif original_by_id.get(entry.barcode_id) != entry.code:
                service.update_barcode(entry.barcode_id, entry.code)

    def _load_existing_product(self, product: ProductDTO) -> None:
        self._sku_edit.setText(product.sku)
        self._name_edit.setText(product.name)
        self._description_edit.setPlainText(product.description or "")
        category_index = self._category_combo.findData(product.category_id)
        if category_index >= 0:
            self._category_combo.setCurrentIndex(category_index)
        type_index = self._type_combo.findData(product.product_type)
        if type_index >= 0:
            self._type_combo.setCurrentIndex(type_index)
        self._unit_price_edit.setText(str(product.unit_price))
        self._cost_price_edit.setText(str(product.cost_price))
        sale_unit_index = self._sale_unit_combo.findData(product.sale_unit)
        if sale_unit_index >= 0:
            self._sale_unit_combo.setCurrentIndex(sale_unit_index)
        self._min_weight_edit.setText(
            str(product.min_weight) if product.min_weight is not None else ""
        )
        self._max_weight_edit.setText(
            str(product.max_weight) if product.max_weight is not None else ""
        )
        self._weight_decimal_places_edit.setText(
            str(product.weight_decimal_places)
            if product.weight_decimal_places is not None
            else ""
        )
        self._update_weight_fields_visibility()
        self._update_price_label()
        self._track_inventory_check.setChecked(product.track_inventory)
        if product.image_path:
            self._set_image_preview(product.image_path)
        self._original_barcodes = self._view_model.product_service.list_barcodes(product.id)
        self._staged_barcodes = [
            _StagedBarcode(barcode_id=b.id, code=b.code) for b in self._original_barcodes
        ]
        self._barcode_edit.setText(self._staged_barcodes[0].code if self._staged_barcodes else "")
        self._render_barcode_list()

    def _clear_field_errors(self) -> None:
        self._form_error.setVisible(False)
        self._sku_error.setVisible(False)
        self._name_error.setVisible(False)
        self._price_error.setVisible(False)
        self._barcode_error.setVisible(False)
        self._weight_error.setVisible(False)

    def _set_field_error(self, label: QLabel, message: str) -> None:
        label.setText(message)
        label.setVisible(True)

    def _parse_prices(self) -> tuple[Decimal, Decimal] | None:
        try:
            unit_price = Decimal(self._unit_price_edit.text() or "0")
            cost_price = Decimal(self._cost_price_edit.text() or "0")
        except InvalidOperation:
            self._set_field_error(self._price_error, "Los precios deben ser números válidos.")
            return None
        if unit_price < 0 or cost_price < 0:
            self._set_field_error(self._price_error, "Los precios no pueden ser negativos.")
            return None
        return unit_price, cost_price

    def _parse_weight_fields(self) -> tuple[Decimal | None, Decimal | None, int | None] | None:
        """`None` = error ya mostrado en `_weight_error`. Campos vacíos son
        válidos (límite/decimales opcionales)."""
        if self._sale_unit_combo.currentData() is not SaleUnit.WEIGHT:
            return None, None, None
        min_text = self._min_weight_edit.text().strip()
        max_text = self._max_weight_edit.text().strip()
        try:
            min_weight = Decimal(min_text) if min_text else None
            max_weight = Decimal(max_text) if max_text else None
        except InvalidOperation:
            self._set_field_error(
                self._weight_error, "El peso mínimo/máximo debe ser un número válido."
            )
            return None
        decimals_text = self._weight_decimal_places_edit.text().strip()
        weight_decimal_places: int | None = None
        if decimals_text:
            try:
                weight_decimal_places = int(decimals_text)
            except ValueError:
                self._set_field_error(
                    self._weight_error, "Los decimales de peso deben ser un número entero."
                )
                return None
        if min_weight is not None and min_weight < 0:
            self._set_field_error(self._weight_error, "El peso mínimo no puede ser negativo.")
            return None
        if max_weight is not None and max_weight < 0:
            self._set_field_error(self._weight_error, "El peso máximo no puede ser negativo.")
            return None
        if min_weight is not None and max_weight is not None and max_weight <= min_weight:
            self._set_field_error(
                self._weight_error, "El peso máximo debe ser mayor al peso mínimo."
            )
            return None
        if weight_decimal_places is not None and not (0 <= weight_decimal_places <= 4):
            self._set_field_error(
                self._weight_error, "Los decimales de peso deben estar entre 0 y 4."
            )
            return None
        return min_weight, max_weight, weight_decimal_places

    def _validate_client_side(self) -> bool:
        is_valid = True
        if not self._sku_edit.text().strip():
            self._set_field_error(self._sku_error, "El SKU es obligatorio.")
            is_valid = False
        if not self._name_edit.text().strip():
            self._set_field_error(self._name_error, "El nombre es obligatorio.")
            is_valid = False
        if self._parse_prices() is None:
            is_valid = False
        if self._parse_weight_fields() is None:
            is_valid = False
        return is_valid

    def _route_server_error(self, message: str) -> None:
        lowered = message.lower()
        if "sku" in lowered:
            self._set_field_error(self._sku_error, message)
        elif "peso" in lowered:
            self._set_field_error(self._weight_error, message)
        elif "precio" in lowered:
            self._set_field_error(self._price_error, message)
        elif "nombre" in lowered:
            self._set_field_error(self._name_error, message)
        else:
            self._set_field_error(self._form_error, message)

    def _sync_primary_barcode(self, code: str) -> None:
        """Reconcilia el campo principal con `_staged_barcodes[0]` justo
        antes de guardar — el resto del formulario (`_apply_staged_barcodes`)
        sigue viendo una sola lista, sin distinguir "principal" de
        "adicional"."""
        if code:
            if self._staged_barcodes:
                self._staged_barcodes[0].code = code
            else:
                self._staged_barcodes.insert(0, _StagedBarcode(barcode_id=None, code=code))
        elif self._staged_barcodes:
            del self._staged_barcodes[0]

    def _on_accept_clicked(self) -> None:
        self._clear_field_errors()
        if not self._validate_client_side():
            return
        prices = self._parse_prices()
        assert prices is not None
        unit_price, cost_price = prices
        weight_fields = self._parse_weight_fields()
        assert weight_fields is not None
        min_weight, max_weight, weight_decimal_places = weight_fields

        barcode_code = self._barcode_edit.text().strip()
        if barcode_code:
            if len(barcode_code) > MAX_BARCODE_LENGTH:
                self._set_field_error(self._barcode_error, _BARCODE_TOO_LONG_MESSAGE)
                return
            exclude_id = self._staged_barcodes[0].barcode_id if self._staged_barcodes else None
            conflict = self._view_model.product_service.find_barcode_conflict(
                barcode_code, exclude_barcode_id=exclude_id
            )
            if conflict is not None:
                self._set_field_error(
                    self._barcode_error, _BARCODE_CONFLICT_MESSAGE.format(name=conflict.name)
                )
                return
        else:
            proceed = QMessageBox.question(
                self,
                "Código de barras",
                "No se ha registrado un código de barras para este producto. "
                "¿Deseas continuar sin código?",
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return
        self._sync_primary_barcode(barcode_code)

        values = {
            "sku": self._sku_edit.text().strip(),
            "name": self._name_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip() or None,
            "category_id": self._category_combo.currentData(),
            "product_type": self._type_combo.currentData(),
            "unit_price": unit_price,
            "cost_price": cost_price,
            "unit_of_measure": _UNIT_OF_MEASURE_BY_SALE_UNIT[self._sale_unit_combo.currentData()],
            "track_inventory": self._track_inventory_check.isChecked(),
            "image_path": self._image_path,
            "sale_unit": self._sale_unit_combo.currentData(),
            "min_weight": min_weight,
            "max_weight": max_weight,
            "weight_decimal_places": weight_decimal_places,
        }

        try:
            if self._existing_product is None:
                created = self._view_model.create_product(**values)
                self._apply_staged_barcodes(created.id)
            else:
                self._view_model.update_product(self._existing_product.id, **values)
                self._apply_staged_barcodes(self._existing_product.id)
        except DomainError as error:
            self._route_server_error(str(error))
            return
        if self._staged_barcodes or self._original_barcodes:
            # Los códigos se aplicaron después de crear/actualizar el
            # producto — recarga para que Catálogo los muestre de inmediato.
            self._view_model.load()

        self.accept()
