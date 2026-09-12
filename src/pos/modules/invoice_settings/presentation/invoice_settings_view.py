"""Pantalla de configuración de factura (Administración → Configuración de
factura): editor visual de plantillas. Tres columnas — izquierda, la
configuración de siempre (empresa, papel, contenido); centro, el lienzo
interactivo (`InvoiceCanvasWidget`) que dibuja el mismo plano de layout
que usa el PDF real (`billing/infrastructure/pdf_renderer.py`), con
controles de zoom y cuadrícula; derecha, el panel de propiedades que
aparece al hacer clic sobre cualquier elemento del lienzo, como en Word.

Todo cambio se refleja de inmediato en el lienzo sin necesidad de
guardar — el mismo patrón de siempre (`_on_form_changed`), ahora también
disparado por el panel de propiedades y por arrastrar el orden del
contenido."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos.modules.invoice_settings.application.content_items import CONTENT_KEYS, CONTENT_LABELS
from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.enums import PAGE_DIMENSIONS_MM, Orientation, PaperSize
from pos.modules.invoice_settings.domain.template_style import (
    ElementStyle,
    ImageStyle,
    TableStyle,
    TemplateConfig,
)
from pos.modules.invoice_settings.presentation.element_properties_panel import (
    ElementPropertiesPanel,
    panel_kind_for,
)
from pos.modules.invoice_settings.presentation.invoice_canvas_widget import InvoiceCanvasWidget
from pos.modules.invoice_settings.presentation.invoice_settings_view_model import (
    InvoiceSettingsViewModel,
)
from pos.modules.invoice_settings.presentation.printer_discovery import (
    list_printer_names,
    list_supported_page_sizes,
)
from pos.shared_ui.image_storage import save_configured_image
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.toast import show_toast

_FIXED_PAPER_SIZE_LABELS: dict[PaperSize, str] = {
    PaperSize.LETTER: "Carta",
    PaperSize.HALF_LETTER: "Media carta",
    PaperSize.OFICIO: "Oficio",
    PaperSize.LEGAL: "Legal",
    PaperSize.EXECUTIVE: "Ejecutivo",
    PaperSize.TABLOID: "Tabloide",
    PaperSize.A4: "A4",
    PaperSize.A5: "A5",
    PaperSize.TICKET_58: "Ticket 58 mm",
    PaperSize.TICKET_80: "Ticket 80 mm",
    PaperSize.TICKET_112: "Ticket 112 mm",
}
_CUSTOM_LABEL = "Ticket personalizado"
_NO_PRINTER_LABEL = "(Ninguna)"
_LOGO_SUBDIR = "invoice_logos"
_LOGO_PREVIEW_SIZE = 96
_IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.bmp)"
_SIZE_MATCH_TOLERANCE_MM = 1.0
_PREVIEW_LABEL_STYLE = "font-size: 13pt; font-weight: 600;"

_GROUPED_STYLE_KEYS = {
    "company_name", "company_nit", "company_address", "company_city", "company_phone",
    "company_email", "company_website", "invoice_number", "issued_at",
    "customer_name", "customer_document",
}
"""`style_key`s seleccionables individualmente (ej. "Factura N.º", "NIT")
que pertenecen a un grupo fijo de `content_order` ("company"/"customer")
— se pueden mover con las flechas del teclado (micro-posicionamiento
propio, por su propio `style_key`), pero no tienen una fila propia que
reordenar con ▲▼: ese botón movería el grupo entero, no a ellos solos,
así que quedan deshabilitados en vez de mover algo que no es lo que el
usuario seleccionó. `"totals"` (Subtotal/Descuento/Impuestos/Total
fusionados en una tabla) e `"items_table"` tampoco tienen una fila propia
de `content_order` que reordenar — su posición es siempre fija, pegada
entre sí (ver `layout_plan.py::build_layout_plan`) — mismo trato."""

_FIXED_POSITION_STYLE_KEYS = {"totals", "items_table", "company"}


def _content_key_for_style_key(style_key: str) -> str | None:
    """`None` si `style_key` no tiene una fila propia en `content_order`
    para reordenar (ver `_GROUPED_STYLE_KEYS`/`_FIXED_POSITION_STYLE_KEYS`);
    de lo contrario, el `style_key` ya ES la clave de `content_order` (así
    es como se construyen hoy — ver `_content_block_for_key` en
    `layout_plan.py`)."""
    if style_key in _FIXED_POSITION_STYLE_KEYS or style_key in _GROUPED_STYLE_KEYS:
        return None
    return style_key

_DEFAULT_IMAGE_SIZE_PT = {
    "logo": (140.0, 70.0),
    "qr": (90.0, 90.0),
    "barcode": (200.0, 50.0),
}

_ZOOM_PRESETS = [50, 75, 100, 125, 150, 200]


def _section_form() -> QFormLayout:
    """`QFormLayout` con ajuste de fila para pantallas angostas: la
    etiqueta pasa arriba del campo en vez de forzar la fila a ensancharse
    — es lo que evita el scroll horizontal en el panel izquierdo."""
    form = QFormLayout()
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    return form


def _group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    return box, layout


class InvoiceSettingsView(QWidget):
    def __init__(
        self, view_model: InvoiceSettingsViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._logo_path: str | None = None
        self._content_order: list[str] = list(CONTENT_KEYS)
        self._template: TemplateConfig = TemplateConfig()
        self._selected_style_key: str | None = None
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.addWidget(make_section_title("Configuración de factura"))

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_config_panel())
        splitter.addWidget(self._build_canvas_panel())
        splitter.addWidget(self._build_properties_panel())
        splitter.setSizes([420, 640, 320])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        outer.addWidget(splitter, stretch=1)

    def _build_config_panel(self) -> QWidget:
        panel = QWidget(self)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        scroll, content_layout = build_scrollable_page(panel)
        content_layout.addWidget(self._build_company_group())
        content_layout.addWidget(self._build_paper_group())
        content_layout.addWidget(self._build_content_group())
        content_layout.addStretch()
        panel_layout.addWidget(scroll, stretch=1)

        self._save_button = QPushButton("Guardar configuración")
        self._restore_design_button = QPushButton("Restaurar diseño original")
        panel_layout.addWidget(self._restore_design_button)
        panel_layout.addWidget(self._save_button)
        return panel

    def _build_company_group(self) -> QGroupBox:
        box, layout = _group("Datos de la empresa")
        form = _section_form()
        self._company_name_edit = QLineEdit(self)
        self._company_nit_edit = QLineEdit(self)
        self._company_address_edit = QLineEdit(self)
        self._company_city_edit = QLineEdit(self)
        self._company_phone_edit = QLineEdit(self)
        self._company_email_edit = QLineEdit(self)
        self._company_website_edit = QLineEdit(self)
        form.addRow("Nombre de la empresa", self._company_name_edit)
        form.addRow("NIT", self._company_nit_edit)
        form.addRow("Dirección", self._company_address_edit)
        form.addRow("Ciudad", self._company_city_edit)
        form.addRow("Teléfono", self._company_phone_edit)
        form.addRow("Correo", self._company_email_edit)
        form.addRow("Sitio web", self._company_website_edit)
        layout.addLayout(form)
        return box

    def _build_paper_group(self) -> QGroupBox:
        box, layout = _group("Papel e impresión")
        form = _section_form()

        self._printer_combo = QComboBox(self)
        self._printer_combo.addItem(_NO_PRINTER_LABEL, userData=None)
        for name in list_printer_names():
            self._printer_combo.addItem(name, userData=name)
        form.addRow("Impresora", self._printer_combo)

        self._paper_size_combo = QComboBox(self)
        form.addRow("Tamaño de impresión", self._paper_size_combo)

        self._custom_width_spin = QDoubleSpinBox(self)
        self._custom_width_spin.setRange(10.0, 1000.0)
        self._custom_width_spin.setSuffix(" mm")
        self._custom_width_spin.setValue(80.0)
        self._custom_height_spin = QDoubleSpinBox(self)
        self._custom_height_spin.setRange(10.0, 2000.0)
        self._custom_height_spin.setSuffix(" mm")
        self._custom_height_spin.setValue(200.0)
        self._custom_size_row = QWidget(self)
        custom_size_layout = QHBoxLayout(self._custom_size_row)
        custom_size_layout.setContentsMargins(0, 0, 0, 0)
        custom_size_layout.addWidget(QLabel("Ancho"))
        custom_size_layout.addWidget(self._custom_width_spin)
        custom_size_layout.addWidget(QLabel("Alto"))
        custom_size_layout.addWidget(self._custom_height_spin)
        self._custom_size_form_label = QLabel("Tamaño personalizado")
        form.addRow(self._custom_size_form_label, self._custom_size_row)

        self._orientation_combo = QComboBox(self)
        self._orientation_combo.addItem("Vertical", userData=Orientation.PORTRAIT)
        self._orientation_combo.addItem("Horizontal", userData=Orientation.LANDSCAPE)
        form.addRow("Orientación", self._orientation_combo)

        self._font_size_spin = QSpinBox(self)
        self._font_size_spin.setRange(6, 24)
        self._font_size_spin.setSuffix(" pt")
        form.addRow("Tamaño de fuente", self._font_size_spin)

        layout.addLayout(form)

        margins_label = QLabel("Márgenes")
        layout.addWidget(margins_label)
        self._margin_top_spin = self._make_margin_spin()
        self._margin_right_spin = self._make_margin_spin()
        self._margin_bottom_spin = self._make_margin_spin()
        self._margin_left_spin = self._make_margin_spin()
        margins_grid = QGridLayout()
        margins_grid.addWidget(QLabel("Arriba"), 0, 0)
        margins_grid.addWidget(self._margin_top_spin, 0, 1)
        margins_grid.addWidget(QLabel("Derecha"), 0, 2)
        margins_grid.addWidget(self._margin_right_spin, 0, 3)
        margins_grid.addWidget(QLabel("Abajo"), 1, 0)
        margins_grid.addWidget(self._margin_bottom_spin, 1, 1)
        margins_grid.addWidget(QLabel("Izquierda"), 1, 2)
        margins_grid.addWidget(self._margin_left_spin, 1, 3)
        layout.addLayout(margins_grid)

        self._populate_paper_size_combo()
        return box

    def _build_content_group(self) -> QGroupBox:
        box, layout = _group("Contenido de la factura")

        logo_row = QHBoxLayout()
        self._logo_preview = QLabel("Sin logo", self)
        self._logo_preview.setFixedSize(_LOGO_PREVIEW_SIZE, _LOGO_PREVIEW_SIZE)
        self._logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._select_logo_button = QPushButton("Seleccionar logo")
        self._remove_logo_button = QPushButton("Quitar logo")
        logo_row.addWidget(self._logo_preview)
        logo_row.addWidget(self._select_logo_button, stretch=1)
        logo_row.addWidget(self._remove_logo_button, stretch=1)
        layout.addWidget(QLabel("Logo"))
        layout.addLayout(logo_row)

        layout.addWidget(QLabel("Orden del contenido (arrastrá para reordenar):"))
        self._content_list = QListWidget(self)
        self._content_list.setMinimumHeight(260)
        self._content_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        layout.addWidget(self._content_list)

        layout.addWidget(QLabel("Totales (posición fija, siempre junto a la tabla de productos):"))
        self._show_discounts_check = QCheckBox("Mostrar descuento", self)
        self._show_taxes_check = QCheckBox("Mostrar impuesto", self)
        self._show_total_check = QCheckBox("Mostrar total", self)
        for checkbox in (self._show_discounts_check, self._show_taxes_check, self._show_total_check):
            checkbox.toggled.connect(self._on_form_changed)
            layout.addWidget(checkbox)
        """Descuento/Impuesto/Total ya no son filas de `_content_list`: su
        posición es siempre fija, pegada a la tabla de productos/Subtotal
        (ver `layout_plan.py::build_layout_plan`) — estas casillas solo
        controlan si se muestran, nunca dónde."""

        text_form = _section_form()
        self._closing_message_edit = QTextEdit(self)
        self._closing_message_edit.setMaximumHeight(70)
        self._social_media_edit = QTextEdit(self)
        self._social_media_edit.setMaximumHeight(70)
        self._return_policy_edit = QTextEdit(self)
        self._return_policy_edit.setMaximumHeight(70)
        text_form.addRow("Mensaje final", self._closing_message_edit)
        text_form.addRow("Redes sociales", self._social_media_edit)
        text_form.addRow("Política de devolución", self._return_policy_edit)
        layout.addLayout(text_form)

        return box

    def _build_canvas_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        preview_label = QLabel("Vista previa", panel)
        preview_label.setStyleSheet(_PREVIEW_LABEL_STYLE)
        layout.addWidget(preview_label)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom:"))
        for percent in _ZOOM_PRESETS:
            button = QPushButton(f"{percent}%", panel)
            button.clicked.connect(lambda _checked, p=percent: self._set_zoom(p))
            zoom_row.addWidget(button)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal, panel)
        self._zoom_slider.setRange(25, 300)
        self._zoom_slider.setValue(100)
        self._zoom_slider.valueChanged.connect(self._set_zoom)
        zoom_row.addWidget(self._zoom_slider, stretch=1)
        self._grid_checkbox = QCheckBox("Mostrar cuadrícula", panel)
        self._grid_checkbox.toggled.connect(self._on_grid_toggled)
        zoom_row.addWidget(self._grid_checkbox)
        layout.addLayout(zoom_row)

        self._canvas = InvoiceCanvasWidget(panel)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._canvas, stretch=1)
        return panel

    def _build_properties_panel(self) -> QWidget:
        panel = QWidget(self)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Propiedades", panel)
        title.setStyleSheet(_PREVIEW_LABEL_STYLE)
        outer.addWidget(title)

        scroll_area, layout = build_scrollable_page(panel)
        outer.addWidget(scroll_area)
        self._properties_panel = ElementPropertiesPanel(panel)
        layout.addWidget(self._properties_panel)
        return panel

    def _make_margin_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(0.0, 80.0)
        spin.setSuffix(" mm")
        spin.setValue(8.0)
        return spin

    def _populate_paper_size_combo(self, printer_name: str | None = None) -> None:
        previous_data = (
            self._paper_size_combo.currentData() if self._paper_size_combo.count() else None
        )
        self._paper_size_combo.blockSignals(True)
        self._paper_size_combo.clear()
        for size, label in _FIXED_PAPER_SIZE_LABELS.items():
            self._paper_size_combo.addItem(label, userData=size)
        self._paper_size_combo.addItem(_CUSTOM_LABEL, userData=PaperSize.CUSTOM)

        if printer_name:
            existing_dims = [PAGE_DIMENSIONS_MM[size] for size in _FIXED_PAPER_SIZE_LABELS]
            new_entries = []
            for label, width_mm, height_mm in list_supported_page_sizes(printer_name):
                already_covered = any(
                    abs(width_mm - dims[0]) < _SIZE_MATCH_TOLERANCE_MM
                    and abs(height_mm - dims[1]) < _SIZE_MATCH_TOLERANCE_MM
                    for dims in existing_dims
                )
                if not already_covered:
                    new_entries.append((label, width_mm, height_mm))
            if new_entries:
                self._paper_size_combo.insertSeparator(self._paper_size_combo.count())
                for label, width_mm, height_mm in new_entries:
                    self._paper_size_combo.addItem(
                        f"{label} (impresora)", userData=(PaperSize.CUSTOM, width_mm, height_mm)
                    )

        if previous_data is not None:
            index = self._paper_size_combo.findData(previous_data)
            if index >= 0:
                self._paper_size_combo.setCurrentIndex(index)
        self._paper_size_combo.blockSignals(False)
        self._update_custom_size_visibility()

    # ------------------------------------------------------------- signals

    def _connect_signals(self) -> None:
        self._select_logo_button.clicked.connect(self._on_select_logo_clicked)
        self._remove_logo_button.clicked.connect(self._on_remove_logo_clicked)
        self._save_button.clicked.connect(self._on_save_clicked)
        self._restore_design_button.clicked.connect(self._on_restore_design_clicked)
        self._content_list.itemChanged.connect(lambda _item: self._on_content_changed())
        self._content_list.model().rowsMoved.connect(lambda *_args: self._on_content_changed())

        for field in (
            self._company_name_edit,
            self._company_nit_edit,
            self._company_address_edit,
            self._company_city_edit,
            self._company_phone_edit,
            self._company_email_edit,
            self._company_website_edit,
        ):
            field.textChanged.connect(self._on_form_changed)
        for text_edit in (
            self._closing_message_edit,
            self._social_media_edit,
            self._return_policy_edit,
        ):
            text_edit.textChanged.connect(self._on_form_changed)

        self._printer_combo.currentIndexChanged.connect(self._on_printer_changed)
        self._paper_size_combo.currentIndexChanged.connect(self._on_paper_size_changed)
        self._orientation_combo.currentIndexChanged.connect(self._on_form_changed)
        self._font_size_spin.valueChanged.connect(self._on_form_changed)
        for spin in (
            self._margin_top_spin,
            self._margin_right_spin,
            self._margin_bottom_spin,
            self._margin_left_spin,
            self._custom_width_spin,
            self._custom_height_spin,
        ):
            spin.valueChanged.connect(self._on_form_changed)

        self._canvas.element_selected.connect(self._on_element_selected)
        self._canvas.spacing_offset_changed.connect(self._on_spacing_offset_changed)
        self._canvas.logo_position_changed.connect(self._on_logo_position_changed)
        self._canvas.logo_double_clicked.connect(self._on_select_logo_clicked)
        self._properties_panel.element_style_changed.connect(self._on_element_style_changed)
        self._properties_panel.image_style_changed.connect(self._on_image_style_changed)
        self._properties_panel.table_style_changed.connect(self._on_table_style_changed)
        self._properties_panel.move_up_requested.connect(lambda: self._on_move_selected(-1))
        self._properties_panel.move_down_requested.connect(lambda: self._on_move_selected(1))

        self._view_model.settings_loaded.connect(self._on_settings_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_printer_changed(self) -> None:
        printer_name = self._printer_combo.currentData()
        self._populate_paper_size_combo(printer_name)
        self._on_form_changed()

    def _on_paper_size_changed(self) -> None:
        data = self._paper_size_combo.currentData()
        if isinstance(data, tuple):
            _, width_mm, height_mm = data
            self._custom_width_spin.blockSignals(True)
            self._custom_height_spin.blockSignals(True)
            self._custom_width_spin.setValue(width_mm)
            self._custom_height_spin.setValue(height_mm)
            self._custom_width_spin.blockSignals(False)
            self._custom_height_spin.blockSignals(False)
        self._update_custom_size_visibility()
        self._on_form_changed()

    def _update_custom_size_visibility(self) -> None:
        is_custom = self._current_paper_size() is PaperSize.CUSTOM
        self._custom_size_row.setVisible(is_custom)
        self._custom_size_form_label.setVisible(is_custom)

    def _current_paper_size(self) -> PaperSize:
        data = self._paper_size_combo.currentData()
        if isinstance(data, tuple):
            return data[0]
        return data if data is not None else PaperSize.LETTER

    def _on_settings_loaded(self, settings: InvoiceSettingsDTO) -> None:
        self._logo_path = settings.logo_path
        self._set_logo_preview(settings.logo_path)
        self._template = settings.template
        self._company_name_edit.setText(settings.company_name)
        self._company_nit_edit.setText(settings.company_nit or "")
        self._company_address_edit.setText(settings.company_address or "")
        self._company_city_edit.setText(settings.company_city or "")
        self._company_phone_edit.setText(settings.company_phone or "")
        self._company_email_edit.setText(settings.company_email or "")
        self._company_website_edit.setText(settings.company_website or "")

        printer_index = self._printer_combo.findData(settings.printer_name)
        self._printer_combo.setCurrentIndex(printer_index if printer_index >= 0 else 0)
        self._populate_paper_size_combo(settings.printer_name)

        size_index = self._paper_size_combo.findData(settings.paper_size)
        if size_index >= 0:
            self._paper_size_combo.setCurrentIndex(size_index)
        if settings.custom_width_mm:
            self._custom_width_spin.setValue(settings.custom_width_mm)
        if settings.custom_height_mm:
            self._custom_height_spin.setValue(settings.custom_height_mm)
        self._update_custom_size_visibility()

        orientation_index = self._orientation_combo.findData(settings.orientation)
        if orientation_index >= 0:
            self._orientation_combo.setCurrentIndex(orientation_index)
        self._font_size_spin.setValue(settings.base_font_size_pt)
        self._margin_top_spin.setValue(settings.margin_top_mm)
        self._margin_right_spin.setValue(settings.margin_right_mm)
        self._margin_bottom_spin.setValue(settings.margin_bottom_mm)
        self._margin_left_spin.setValue(settings.margin_left_mm)

        self._closing_message_edit.setPlainText(settings.closing_message or "")
        self._social_media_edit.setPlainText(settings.social_media or "")
        self._return_policy_edit.setPlainText(settings.return_policy or "")

        self._content_order = list(settings.content_order)
        show_flags = {
            "logo": settings.show_logo,
            "customer": settings.show_customer,
            "cashier": settings.show_cashier,
            "register": settings.show_register,
            "date": settings.show_date,
            "time": settings.show_time,
            "qr": settings.show_qr,
            "barcode": settings.show_barcode,
            "closing_message": settings.show_closing_message,
            "social_media": settings.show_social_media,
            "return_policy": settings.show_return_policy,
        }
        self._rebuild_content_list(show_flags)
        self._show_discounts_check.setChecked(settings.show_discounts)
        self._show_taxes_check.setChecked(settings.show_taxes)
        self._show_total_check.setChecked(settings.show_total)
        self._selected_style_key = None
        self._properties_panel.show_nothing()
        self._on_form_changed()

    def _rebuild_content_list(self, show_flags: dict[str, bool]) -> None:
        self._content_list.blockSignals(True)
        self._content_list.clear()
        for key in self._content_order:
            item = QListWidgetItem(CONTENT_LABELS.get(key, key))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if show_flags.get(key) else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._content_list.addItem(item)
        self._content_list.blockSignals(False)

    def _on_content_changed(self) -> None:
        self._content_order = [
            self._content_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._content_list.count())
        ]
        self._on_form_changed()

    def _on_select_logo_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar logo", "", _IMAGE_FILTER)
        if not path:
            return
        self._logo_path = save_configured_image(Path(path), _LOGO_SUBDIR)
        self._set_logo_preview(self._logo_path)
        self._on_form_changed()

    def _on_remove_logo_clicked(self) -> None:
        self._logo_path = None
        self._set_logo_preview(None)
        self._on_form_changed()

    def _set_logo_preview(self, path: str | None) -> None:
        if not path:
            # `setPixmap()` después de `setText()` le hace olvidar el texto a
            # `QLabel` (pasa a modo "pixmap", aunque el pixmap esté vacío).
            self._logo_preview.setPixmap(QPixmap())
            self._logo_preview.setText("Sin logo")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._logo_preview.setText("Sin logo")
            return
        self._logo_preview.setText("")
        self._logo_preview.setPixmap(
            pixmap.scaled(
                _LOGO_PREVIEW_SIZE,
                _LOGO_PREVIEW_SIZE,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _current_show_flags(self) -> dict[str, bool]:
        flags = {}
        for i in range(self._content_list.count()):
            item = self._content_list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            flags[key] = item.checkState() == Qt.CheckState.Checked
        return flags

    # ---------------------------------------------------- panel de propiedades

    def _on_element_selected(self, style_key: str) -> None:
        self._selected_style_key = style_key
        kind = panel_kind_for(style_key)
        if kind == "image":
            default_width, default_height = _DEFAULT_IMAGE_SIZE_PT.get(style_key, (100.0, 100.0))
            style = self._template.image_styles.get(style_key, ImageStyle())
            self._properties_panel.show_image(style_key, style, default_width, default_height)
        elif kind == "table":
            style = self._template.table_styles.get(style_key, TableStyle())
            self._properties_panel.show_table(style_key, style)
        else:
            style = self._template.element_styles.get(style_key, ElementStyle())
            self._properties_panel.show_text(style_key, style)
        self._update_move_buttons_enabled(style_key)

    def _update_move_buttons_enabled(self, style_key: str) -> None:
        content_key = _content_key_for_style_key(style_key)
        if content_key is None:
            self._properties_panel.set_move_buttons_enabled(False, False)
            return
        row = self._row_for_content_key(content_key)
        if row is None:
            self._properties_panel.set_move_buttons_enabled(False, False)
            return
        self._properties_panel.set_move_buttons_enabled(
            row > 0, row < self._content_list.count() - 1
        )

    def _row_for_content_key(self, content_key: str) -> int | None:
        for row in range(self._content_list.count()):
            if self._content_list.item(row).data(Qt.ItemDataRole.UserRole) == content_key:
                return row
        return None

    def _on_move_selected(self, direction: int) -> None:
        if self._selected_style_key is None:
            return
        content_key = _content_key_for_style_key(self._selected_style_key)
        if content_key is None:
            return
        row = self._row_for_content_key(content_key)
        if row is None:
            return
        new_row = row + direction
        if not 0 <= new_row < self._content_list.count():
            return
        item = self._content_list.takeItem(row)
        self._content_list.insertItem(new_row, item)
        self._content_list.setCurrentItem(item)
        self._on_content_changed()
        self._update_move_buttons_enabled(self._selected_style_key)

    def _on_spacing_offset_changed(self, style_key: str, offset: float) -> None:
        """El lienzo ya se movió solo (ver `InvoiceCanvasWidget._apply_nudge`)
        — acá solo se refleja el nuevo offset en `self._template` para que
        quede incluido cuando se guarde la configuración, sin pedirle al
        lienzo que se redibuje de nuevo (`_on_form_changed` sí lo haría)."""
        new_offsets = {**self._template.spacing_offsets, style_key: offset}
        self._template = replace(self._template, spacing_offsets=new_offsets)

    def _on_logo_position_changed(self, x_pt: float, y_pt: float) -> None:
        """El lienzo ya movió el logo solo (arrastre nativo de Qt o
        flechas, sin reconstruir la escena) — mismo patrón que
        `_on_spacing_offset_changed`: acá solo se refleja la nueva
        posición en `self._template` (para guardarla) y, si el logo es lo
        seleccionado, en el panel de propiedades — nunca se llama a
        `_on_form_changed()`."""
        logo_style = self._template.image_styles.get("logo", ImageStyle())
        new_style = replace(logo_style, absolute_x_pt=x_pt, absolute_y_pt=y_pt)
        new_styles = {**self._template.image_styles, "logo": new_style}
        self._template = replace(self._template, image_styles=new_styles)
        if self._selected_style_key == "logo":
            self._properties_panel.update_logo_position(x_pt, y_pt)

    def _on_element_style_changed(self, style_key: str, style: ElementStyle) -> None:
        new_styles = {**self._template.element_styles, style_key: style}
        self._template = replace(self._template, element_styles=new_styles)
        self._on_form_changed()

    def _on_image_style_changed(self, style_key: str, style: ImageStyle) -> None:
        new_styles = {**self._template.image_styles, style_key: style}
        self._template = replace(self._template, image_styles=new_styles)
        self._on_form_changed()

    def _on_table_style_changed(self, style_key: str, style: TableStyle) -> None:
        new_styles = {**self._template.table_styles, style_key: style}
        self._template = replace(self._template, table_styles=new_styles)
        self._on_form_changed()

    def _on_restore_design_clicked(self) -> None:
        self._template = TemplateConfig()
        self._selected_style_key = None
        self._properties_panel.show_nothing()
        self._on_form_changed()

    # ---------------------------------------------------------------- zoom

    def _set_zoom(self, percent: int) -> None:
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(percent)
        self._zoom_slider.blockSignals(False)
        self._canvas.set_zoom(percent / 100.0)

    def _on_grid_toggled(self, checked: bool) -> None:
        self._canvas.set_show_grid(checked)

    # ---------------------------------------------------------------- guardar

    def _dto_from_form(self) -> InvoiceSettingsDTO:
        flags = self._current_show_flags()
        is_custom = self._current_paper_size() is PaperSize.CUSTOM
        return InvoiceSettingsDTO(
            company_name=self._company_name_edit.text().strip(),
            company_nit=self._company_nit_edit.text().strip() or None,
            company_address=self._company_address_edit.text().strip() or None,
            company_city=self._company_city_edit.text().strip() or None,
            company_phone=self._company_phone_edit.text().strip() or None,
            company_email=self._company_email_edit.text().strip() or None,
            company_website=self._company_website_edit.text().strip() or None,
            logo_path=self._logo_path,
            paper_size=self._current_paper_size(),
            custom_width_mm=self._custom_width_spin.value() if is_custom else None,
            custom_height_mm=self._custom_height_spin.value() if is_custom else None,
            orientation=self._orientation_combo.currentData() or Orientation.PORTRAIT,
            margin_top_mm=self._margin_top_spin.value(),
            margin_right_mm=self._margin_right_spin.value(),
            margin_bottom_mm=self._margin_bottom_spin.value(),
            margin_left_mm=self._margin_left_spin.value(),
            base_font_size_pt=self._font_size_spin.value(),
            printer_name=self._printer_combo.currentData(),
            show_logo=flags.get("logo", False),
            show_customer=flags.get("customer", False),
            show_cashier=flags.get("cashier", False),
            show_register=flags.get("register", False),
            show_date=flags.get("date", False),
            show_time=flags.get("time", False),
            show_discounts=self._show_discounts_check.isChecked(),
            show_taxes=self._show_taxes_check.isChecked(),
            show_total=self._show_total_check.isChecked(),
            show_qr=flags.get("qr", False),
            show_barcode=flags.get("barcode", False),
            show_closing_message=flags.get("closing_message", False),
            show_social_media=flags.get("social_media", False),
            show_return_policy=flags.get("return_policy", False),
            content_order=list(self._content_order),
            closing_message=self._closing_message_edit.toPlainText().strip() or None,
            social_media=self._social_media_edit.toPlainText().strip() or None,
            return_policy=self._return_policy_edit.toPlainText().strip() or None,
            template=self._template,
        )

    def _on_form_changed(self) -> None:
        self._canvas.set_settings(self._dto_from_form())

    def _on_save_clicked(self) -> None:
        if not self._company_name_edit.text().strip():
            self._show_error("El nombre de la empresa es obligatorio.")
            return
        self._view_model.save(self._dto_from_form())

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
