"""Panel de propiedades del editor visual de plantillas de factura —
aparece al hacer clic sobre cualquier elemento del lienzo (`InvoiceCanvasWidget`),
como en Word. Solo permite modificar apariencia, nunca funcionamiento:
fuente/tamaño/color/negrilla/cursiva/subrayado/mayúsculas-minúsculas/
alineación/espaciado para texto; ancho/alto/alineación/proporción para
imágenes (logo, QR, código de barras); color de encabezado/texto/líneas/
cebra y alto de fila/espaciado de celda para tablas."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pos.modules.invoice_settings.domain.template_style import ElementStyle, ImageStyle, TableStyle
from pos.shared_ui.widgets.color_picker import ColorPickerWidget

FONT_SIZES = [5, 6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 32, 36, 40, 48, 60]

TEXT_STYLE_KEYS = {
    "company_name", "company_nit", "company_address", "company_city", "company_phone",
    "company_website", "invoice_number", "issued_at", "customer_name", "customer_document",
    "cashier", "register", "date", "time", "closing_message", "social_media", "return_policy",
}
IMAGE_STYLE_KEYS = {"logo", "qr", "barcode"}
TABLE_STYLE_KEYS = {"items_table", "totals"}

_ALIGNMENTS = [("Izquierda", "left"), ("Centro", "center"), ("Derecha", "right")]
_CASES = [("Normal", "none"), ("MAYÚSCULAS", "upper"), ("minúsculas", "lower")]

_POSITION_UNSET_SENTINEL = -1.0
"""Valor que representa "sin posición absoluta definida" en los spinbox
X/Y del grupo "Posición" — 0 es una coordenada válida (esquina superior
izquierda de la hoja), así que no sirve como centinela; el arrastre y el
teclado además siempre dejan la posición del logo en ≥0 (ver
`InvoiceCanvasWidget._BlockGraphicsItem.itemChange`), así que -1 nunca
colisiona con un valor real."""
_DEFAULT_KEYBOARD_HINT = (
    "Usa las flechas ↑ ↓ para mover este elemento — Shift = 5 pasos, Ctrl = 10 pasos."
)
_LOGO_KEYBOARD_HINT = (
    "Arrastra el logo con el mouse, o usa las flechas ↑ ↓ ← → para moverlo — "
    "Shift = 10 pasos, Ctrl = 25 pasos."
)


def panel_kind_for(style_key: str) -> str:
    if style_key in IMAGE_STYLE_KEYS:
        return "image"
    if style_key in TABLE_STYLE_KEYS:
        return "table"
    return "text"


class ElementPropertiesPanel(QWidget):
    """Expone una señal por tipo de estilo; la vista decide, según
    `panel_kind_for(style_key)`, qué método `show_*` llamar al
    seleccionar un elemento del lienzo."""

    element_style_changed = Signal(str, object)  # style_key, ElementStyle
    image_style_changed = Signal(str, object)  # style_key, ImageStyle
    table_style_changed = Signal(str, object)  # style_key, TableStyle
    move_up_requested = Signal()
    move_down_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._style_key: str | None = None
        self._updating = False

        layout = QVBoxLayout(self)
        self._title_label = QLabel("Ningún elemento seleccionado")
        self._title_label.setProperty("role", "title")
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        self._keyboard_hint_label = QLabel(_DEFAULT_KEYBOARD_HINT)
        self._keyboard_hint_label.setProperty("role", "secondary")
        self._keyboard_hint_label.setWordWrap(True)
        self._keyboard_hint_label.setVisible(False)
        layout.addWidget(self._keyboard_hint_label)

        move_row = QHBoxLayout()
        self._move_up_button = QPushButton("▲ Subir elemento", self)
        self._move_up_button.setToolTip("Mover este elemento una posición hacia arriba")
        self._move_up_button.clicked.connect(self.move_up_requested)
        self._move_down_button = QPushButton("▼ Bajar elemento", self)
        self._move_down_button.setToolTip("Mover este elemento una posición hacia abajo")
        self._move_down_button.clicked.connect(self.move_down_requested)
        move_row.addWidget(self._move_up_button)
        move_row.addWidget(self._move_down_button)
        layout.addLayout(move_row)
        self.set_move_buttons_enabled(False, False)

        self._stack = QStackedWidget(self)
        self._empty_page = QWidget(self)
        self._text_page = self._build_text_page()
        self._image_page = self._build_image_page()
        self._table_page = self._build_table_page()
        self._stack.addWidget(self._empty_page)
        self._stack.addWidget(self._text_page)
        self._stack.addWidget(self._image_page)
        self._stack.addWidget(self._table_page)
        layout.addWidget(self._stack)
        layout.addStretch()
        self._stack.setCurrentWidget(self._empty_page)

    # -- construcción de páginas -----------------------------------------

    def _build_text_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        self._font_combo = QFontComboBox(page)
        self._font_combo.currentFontChanged.connect(self._on_text_changed)
        form.addRow("Fuente", self._font_combo)

        self._font_size_combo = QComboBox(page)
        for size in FONT_SIZES:
            self._font_size_combo.addItem(f"{size} pt", userData=size)
        self._font_size_combo.currentIndexChanged.connect(self._on_text_changed)
        form.addRow("Tamaño", self._font_size_combo)

        self._color_picker = ColorPickerWidget(page)
        self._color_picker.color_changed.connect(lambda _hex: self._on_text_changed())
        form.addRow("Color", self._color_picker)

        style_row = QHBoxLayout()
        self._bold_button = QPushButton("N", page)
        self._bold_button.setCheckable(True)
        self._bold_button.setToolTip("Negrilla")
        self._italic_button = QPushButton("K", page)
        self._italic_button.setCheckable(True)
        self._italic_button.setToolTip("Cursiva")
        self._underline_button = QPushButton("S", page)
        self._underline_button.setCheckable(True)
        self._underline_button.setToolTip("Subrayado")
        for button in (self._bold_button, self._italic_button, self._underline_button):
            button.toggled.connect(self._on_text_changed)
            style_row.addWidget(button)
        form.addRow("Estilo", style_row)

        self._case_combo = QComboBox(page)
        for label, value in _CASES:
            self._case_combo.addItem(label, userData=value)
        self._case_combo.currentIndexChanged.connect(self._on_text_changed)
        form.addRow("Mayúsculas/minúsculas", self._case_combo)

        self._alignment_combo = QComboBox(page)
        for label, value in _ALIGNMENTS:
            self._alignment_combo.addItem(label, userData=value)
        self._alignment_combo.currentIndexChanged.connect(self._on_text_changed)
        form.addRow("Alineación", self._alignment_combo)

        self._line_spacing_spin = QDoubleSpinBox(page)
        self._line_spacing_spin.setRange(0.5, 3.0)
        self._line_spacing_spin.setSingleStep(0.1)
        self._line_spacing_spin.setValue(1.0)
        self._line_spacing_spin.valueChanged.connect(self._on_text_changed)
        form.addRow("Espaciado entre líneas", self._line_spacing_spin)

        self._space_before_spin = QDoubleSpinBox(page)
        self._space_before_spin.setRange(0.0, 100.0)
        self._space_before_spin.setSuffix(" pt")
        self._space_before_spin.valueChanged.connect(self._on_text_changed)
        form.addRow("Margen antes", self._space_before_spin)

        self._space_after_spin = QDoubleSpinBox(page)
        self._space_after_spin.setRange(0.0, 100.0)
        self._space_after_spin.setSuffix(" pt")
        self._space_after_spin.valueChanged.connect(self._on_text_changed)
        form.addRow("Margen después", self._space_after_spin)

        return page

    def _build_image_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        self._image_width_spin = QDoubleSpinBox(page)
        self._image_width_spin.setRange(1.0, 800.0)
        self._image_width_spin.setSuffix(" pt")
        self._image_width_spin.valueChanged.connect(self._on_image_changed)
        form.addRow("Ancho", self._image_width_spin)

        self._image_height_spin = QDoubleSpinBox(page)
        self._image_height_spin.setRange(1.0, 800.0)
        self._image_height_spin.setSuffix(" pt")
        self._image_height_spin.valueChanged.connect(self._on_image_changed)
        form.addRow("Alto", self._image_height_spin)

        self._image_alignment_combo = QComboBox(page)
        for label, value in _ALIGNMENTS:
            self._image_alignment_combo.addItem(label, userData=value)
        self._image_alignment_combo.currentIndexChanged.connect(self._on_image_changed)
        form.addRow("Alineación", self._image_alignment_combo)

        self._keep_aspect_combo = QComboBox(page)
        self._keep_aspect_combo.addItem("Mantener proporción", userData=True)
        self._keep_aspect_combo.addItem("Estirar", userData=False)
        self._keep_aspect_combo.currentIndexChanged.connect(self._on_image_changed)
        form.addRow("Ajuste", self._keep_aspect_combo)

        self._position_group = QGroupBox("Posición", page)
        position_form = QFormLayout(self._position_group)

        self._position_x_spin = QDoubleSpinBox(page)
        self._position_x_spin.setRange(_POSITION_UNSET_SENTINEL, 3000.0)
        self._position_x_spin.setSuffix(" pt")
        self._position_x_spin.setSpecialValueText("(automático)")
        self._position_x_spin.valueChanged.connect(self._on_image_changed)
        position_form.addRow("X", self._position_x_spin)

        self._position_y_spin = QDoubleSpinBox(page)
        self._position_y_spin.setRange(_POSITION_UNSET_SENTINEL, 3000.0)
        self._position_y_spin.setSuffix(" pt")
        self._position_y_spin.setSpecialValueText("(automático)")
        self._position_y_spin.valueChanged.connect(self._on_image_changed)
        position_form.addRow("Y", self._position_y_spin)

        self._position_group.setVisible(False)
        form.addRow(self._position_group)

        return page

    def _build_table_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        self._header_bg_picker = ColorPickerWidget(page)
        self._header_bg_picker.color_changed.connect(lambda _hex: self._on_table_changed())
        form.addRow("Color de encabezado", self._header_bg_picker)

        self._header_text_picker = ColorPickerWidget(page)
        self._header_text_picker.color_changed.connect(lambda _hex: self._on_table_changed())
        form.addRow("Color de texto del encabezado", self._header_text_picker)

        self._grid_color_picker = ColorPickerWidget(page)
        self._grid_color_picker.color_changed.connect(lambda _hex: self._on_table_changed())
        form.addRow("Color de líneas", self._grid_color_picker)

        self._zebra_color_picker = ColorPickerWidget(page)
        self._zebra_color_picker.color_changed.connect(lambda _hex: self._on_table_changed())
        form.addRow("Color de filas alternadas", self._zebra_color_picker)

        self._row_height_spin = QDoubleSpinBox(page)
        self._row_height_spin.setRange(0.0, 100.0)
        self._row_height_spin.setSuffix(" pt")
        self._row_height_spin.setSpecialValueText("Automático")
        self._row_height_spin.valueChanged.connect(self._on_table_changed)
        form.addRow("Alto de fila", self._row_height_spin)

        self._cell_padding_spin = QDoubleSpinBox(page)
        self._cell_padding_spin.setRange(0.0, 40.0)
        self._cell_padding_spin.setSuffix(" pt")
        self._cell_padding_spin.setSpecialValueText("Automático")
        self._cell_padding_spin.valueChanged.connect(self._on_table_changed)
        form.addRow("Espaciado de celda", self._cell_padding_spin)

        return page

    # -- mostrar un elemento seleccionado ---------------------------------

    def set_move_buttons_enabled(self, can_move_up: bool, can_move_down: bool) -> None:
        """La vista decide esto según la posición real del elemento en el
        orden del contenido — un elemento que es parte de un grupo fijo
        (ej. "Factura N.º" dentro de los datos de la empresa) no tiene un
        lugar propio en ese orden, así que ambos quedan deshabilitados."""
        self._move_up_button.setEnabled(can_move_up)
        self._move_down_button.setEnabled(can_move_down)

    def show_nothing(self) -> None:
        self._style_key = None
        self._title_label.setText("Ningún elemento seleccionado")
        self._keyboard_hint_label.setVisible(False)
        self.set_move_buttons_enabled(False, False)
        self._stack.setCurrentWidget(self._empty_page)

    def show_text(self, style_key: str, style: ElementStyle) -> None:
        self._style_key = style_key
        self._keyboard_hint_label.setText(_DEFAULT_KEYBOARD_HINT)
        self._keyboard_hint_label.setVisible(True)
        self._updating = True
        try:
            self._title_label.setText(f"Propiedades de texto — {style_key}")
            if style.font_family:
                self._font_combo.setCurrentFont(QFont(style.font_family))
            size_index = self._font_size_combo.findData(style.font_size_pt)
            self._font_size_combo.setCurrentIndex(size_index if size_index >= 0 else -1)
            self._color_picker.set_color(style.color_hex or "#000000")
            self._bold_button.setChecked(bool(style.bold))
            self._italic_button.setChecked(style.italic)
            self._underline_button.setChecked(style.underline)
            self._case_combo.setCurrentIndex(self._case_combo.findData(style.letter_case))
            self._alignment_combo.setCurrentIndex(self._alignment_combo.findData(style.alignment))
            self._line_spacing_spin.setValue(style.line_spacing)
            self._space_before_spin.setValue(style.space_before_pt)
            self._space_after_spin.setValue(style.space_after_pt)
        finally:
            self._updating = False
        self._stack.setCurrentWidget(self._text_page)

    def show_image(
        self, style_key: str, style: ImageStyle, default_width: float, default_height: float
    ) -> None:
        self._style_key = style_key
        is_logo = style_key == "logo"
        hint_text = _LOGO_KEYBOARD_HINT if is_logo else _DEFAULT_KEYBOARD_HINT
        self._keyboard_hint_label.setText(hint_text)
        self._keyboard_hint_label.setVisible(True)
        self._updating = True
        try:
            self._title_label.setText(f"Propiedades de imagen — {style_key}")
            self._image_width_spin.setValue(style.width_pt or default_width)
            self._image_height_spin.setValue(style.height_pt or default_height)
            self._image_alignment_combo.setCurrentIndex(
                self._image_alignment_combo.findData(style.align)
            )
            self._keep_aspect_combo.setCurrentIndex(
                self._keep_aspect_combo.findData(style.keep_aspect_ratio)
            )
            self._position_group.setVisible(is_logo)
            if is_logo:
                self._position_x_spin.setValue(
                    style.absolute_x_pt
                    if style.absolute_x_pt is not None
                    else _POSITION_UNSET_SENTINEL
                )
                self._position_y_spin.setValue(
                    style.absolute_y_pt
                    if style.absolute_y_pt is not None
                    else _POSITION_UNSET_SENTINEL
                )
        finally:
            self._updating = False
        self._stack.setCurrentWidget(self._image_page)

    def update_logo_position(self, x_pt: float, y_pt: float) -> None:
        """Llamada por la vista cuando el lienzo emite
        `logo_position_changed` (arrastre con mouse o flechas) — refleja
        el nuevo valor en vivo sin disparar `_on_image_changed` (guard
        `_updating`, mismo patrón que `show_image`). No hace nada si el
        logo no es lo que está mostrando el panel en este momento."""
        if self._style_key != "logo":
            return
        self._updating = True
        try:
            self._position_x_spin.setValue(x_pt)
            self._position_y_spin.setValue(y_pt)
        finally:
            self._updating = False

    def show_table(self, style_key: str, style: TableStyle) -> None:
        self._style_key = style_key
        self._keyboard_hint_label.setText(_DEFAULT_KEYBOARD_HINT)
        self._keyboard_hint_label.setVisible(True)
        self._updating = True
        try:
            self._title_label.setText(f"Propiedades de tabla — {style_key}")
            self._header_bg_picker.set_color(style.header_bg_hex or "#2F6FED")
            self._header_text_picker.set_color(style.header_text_color_hex or "#FFFFFF")
            self._grid_color_picker.set_color(style.grid_color_hex or "#DDDDDD")
            self._zebra_color_picker.set_color(style.zebra_color_hex or "#F5F6F8")
            self._row_height_spin.setValue(style.row_height_pt or 0.0)
            self._cell_padding_spin.setValue(style.cell_padding_pt or 0.0)
        finally:
            self._updating = False
        self._stack.setCurrentWidget(self._table_page)

    # -- emitir cambios ---------------------------------------------------

    def _on_text_changed(self, *_args: object) -> None:
        if self._updating or self._style_key is None:
            return
        style = ElementStyle(
            font_family=self._font_combo.currentFont().family(),
            font_size_pt=self._font_size_combo.currentData(),
            color_hex=self._color_picker.current_color(),
            bold=self._bold_button.isChecked(),
            italic=self._italic_button.isChecked(),
            underline=self._underline_button.isChecked(),
            letter_case=self._case_combo.currentData() or "none",
            alignment=self._alignment_combo.currentData() or "left",
            line_spacing=self._line_spacing_spin.value(),
            space_before_pt=self._space_before_spin.value(),
            space_after_pt=self._space_after_spin.value(),
        )
        self.element_style_changed.emit(self._style_key, style)

    def _on_image_changed(self, *_args: object) -> None:
        if self._updating or self._style_key is None:
            return
        is_logo = self._style_key == "logo"
        # X/Y solo se guardan para el logo — en cualquier otro estilo de
        # imagen (QR/código de barras/imagen de pie) quedan siempre en
        # `None`, así que un valor que haya quedado en los spinbox
        # (ocultos para esos casos) nunca se filtra a su `ImageStyle`.
        position_x = self._position_x_spin.value() if is_logo else _POSITION_UNSET_SENTINEL
        position_y = self._position_y_spin.value() if is_logo else _POSITION_UNSET_SENTINEL
        style = ImageStyle(
            align=self._image_alignment_combo.currentData() or "center",
            width_pt=self._image_width_spin.value(),
            height_pt=self._image_height_spin.value(),
            keep_aspect_ratio=bool(self._keep_aspect_combo.currentData()),
            absolute_x_pt=position_x if position_x > _POSITION_UNSET_SENTINEL else None,
            absolute_y_pt=position_y if position_y > _POSITION_UNSET_SENTINEL else None,
        )
        self.image_style_changed.emit(self._style_key, style)

    def _on_table_changed(self, *_args: object) -> None:
        if self._updating or self._style_key is None:
            return
        style = TableStyle(
            header_bg_hex=self._header_bg_picker.current_color(),
            header_text_color_hex=self._header_text_picker.current_color(),
            grid_color_hex=self._grid_color_picker.current_color(),
            zebra_color_hex=self._zebra_color_picker.current_color(),
            row_height_pt=self._row_height_spin.value() or None,
            cell_padding_pt=self._cell_padding_spin.value() or None,
        )
        self.table_style_changed.emit(self._style_key, style)
