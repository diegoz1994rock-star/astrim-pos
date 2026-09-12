"""Lienzo interactivo de la vista previa — dibuja el mismo `LayoutPlan`
(`invoice_settings.domain.layout_plan`) que `billing/infrastructure/
pdf_renderer.py` traduce a PDF real con ReportLab (mismo contenido, mismo
orden, mismos márgenes/tamaño de página/tamaño de fuente — el único
margen de diferencia posible es el motor de texto exacto), pero ahora
sobre un `QGraphicsScene`: cada bloque es un `QGraphicsItem` clickeable
que, al seleccionarse, emite `element_selected(style_key)` para que la
pantalla abra el panel de propiedades correspondiente — igual que Word.

Todas las medidas se manejan en puntos (pt, 1/72 pulgada) — el mismo
sistema de unidades que ReportLab.

Un cambio de estilo (tamaño de fuente, interlineado, etc.) puede alterar
la altura de un bloque y por lo tanto desplazar todo lo que va después —
por eso cualquier cambio (de estilo o estructural) reconstruye la escena
completa, con el mismo debounce de 120ms que ya tenía la vista previa
anterior; lo que se evita es reconstruir el resto de la ventana (paneles,
barra de zoom, lista de orden), no el lienzo en sí."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView, QWidget

from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.layout_plan import (
    NUDGE_STEP_PT,
    BarcodeBlock,
    Block,
    ImageBlock,
    InvoiceLineItem,
    InvoiceRenderData,
    LayoutPlan,
    QrBlock,
    SpacerBlock,
    TableBlock,
    TextBlock,
    build_layout_plan,
    logo_overlay_block,
)
from pos.modules.invoice_settings.domain.template_style import ImageStyle
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.invoice_block_rendering import (
    BLOCK_GAP_AFTER_PT,
    PT_PER_MM,
    aligned_x,
    build_barcode_block,
    build_image_block,
    build_qr_block,
    build_table_rows,
    build_text_block,
)

_SELECTION_PEN = QPen(QColor("#2F6FED"), 1.5, Qt.PenStyle.DashLine)
_GRID_GUIDE_PEN = QPen(QColor("#E3E7EF"), 0.5)
_GRID_STEP_PT = 20.0

_MIN_ZOOM = 0.25
_MAX_ZOOM = 3.0

_LOGO_OVERLAY_Z_VALUE = 1000.0
"""Se dibuja por encima de cualquier otro bloque (tablas, QR, código de
barras, texto) — ninguno de esos define un `zValue` propio (quedan en 0
por defecto), así que cualquier valor claramente positivo alcanza."""

_LOGO_NUDGE_STEP_PT = 1.0
_LOGO_NUDGE_SHIFT_STEP_PT = 10.0
_LOGO_NUDGE_CTRL_STEP_PT = 25.0
"""Pasos de teclado exclusivos del logo — distintos de `NUDGE_STEP_PT`
(1/5/10, usado por el micro-posicionamiento de texto): acá se pidió
1/10/25, y en las 4 direcciones en vez de solo vertical."""

_LOGO_ARROW_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right)


def _logo_step_count(modifiers: Qt.KeyboardModifier) -> float:
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        return _LOGO_NUDGE_CTRL_STEP_PT
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        return _LOGO_NUDGE_SHIFT_STEP_PT
    return _LOGO_NUDGE_STEP_PT

_SAMPLE_ITEMS = [
    InvoiceLineItem(
        "Café", "2",
        format_currency(Decimal("5000")), format_currency(Decimal("0")),
        format_currency(Decimal("950")), format_currency(Decimal("10950")),
    ),
    InvoiceLineItem(
        "Croissant", "1",
        format_currency(Decimal("4500")), format_currency(Decimal("500")),
        format_currency(Decimal("760")), format_currency(Decimal("4760")),
    ),
    InvoiceLineItem(
        "Jugo natural", "1",
        format_currency(Decimal("6000")), format_currency(Decimal("0")),
        format_currency(Decimal("1140")), format_currency(Decimal("7140")),
    ),
]
_SAMPLE_RENDER_DATA = InvoiceRenderData(
    invoice_number="F-000001",
    issued_at_label="13/07/2026 19:30",
    customer_name="Carlos Pérez",
    customer_document="CC 1.234.567",
    cashier_name="Ana Cajera",
    register_name="Caja 1",
    date_label="13/07/2026",
    time_label="07:30 p. m.",
    items=_SAMPLE_ITEMS,
    subtotal_label=format_currency(Decimal("15500")),
    discount_label=format_currency(Decimal("500")),
    tax_label=format_currency(Decimal("2850")),
    total_label=format_currency(Decimal("18350")),
)

def _step_count(modifiers: Qt.KeyboardModifier) -> int:
    """↑/↓ solas mueven 1 paso; Shift mueve 5; Ctrl mueve 10 — tal como se
    pidió. Ctrl tiene prioridad si por algún motivo llegan ambos."""
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        return 10
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        return 5
    return 1


class _BlockGraphicsItem(QGraphicsItem):
    """Un bloque del `LayoutPlan` dibujado dentro de su propio
    `boundingRect` local — clickeable/seleccionable, expone `style_key`
    para que la vista sepa qué panel de propiedades abrir.

    `on_moved`/`on_double_click`/`clamp_position` son exclusivos del logo
    (ver `InvoiceCanvasWidget._make_logo_movable`) — para cualquier otro
    bloque quedan en `None`/`False` y estos overrides no hacen nada
    distinto de lo que ya hacía Qt por defecto."""

    def __init__(
        self,
        rect: QRectF,
        style_key: str,
        paint_fn,
        *,
        on_moved=None,
        on_double_click=None,
        clamp_position: bool = False,
    ) -> None:
        super().__init__()
        self._rect = rect
        self.style_key = style_key
        self._paint_fn = paint_fn
        self._on_moved = on_moved
        self._on_double_click = on_double_click
        self._clamp_position = clamp_position
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        """Sin este flag, Qt nunca llama a `itemChange` para cambios de
        posición (optimización por defecto de `QGraphicsItem`) — ni el
        clamp a coordenadas no negativas ni `_on_moved` (que sincroniza
        `_logo_overlay_item` y emite `logo_position_changed`) se disparaban
        nunca, aunque el resto de la lógica de arrastre estuviera bien."""

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        return self._rect

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_fn(painter, self._rect)
        if self.isSelected():
            painter.setPen(_SELECTION_PEN)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._rect)

    def itemChange(self, change, value):  # noqa: N802 (Qt override)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._clamp_position:
            point = value
            return QPointF(max(0.0, point.x()), max(0.0, point.y()))
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self._on_moved:
            self._on_moved(value)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._on_double_click:
            self._on_double_click()
        super().mouseDoubleClickEvent(event)


class InvoiceCanvasWidget(QGraphicsView):
    """Lienzo interactivo: `set_settings()` reconstruye la escena con un
    debounce de 120ms; clic en un bloque selecciona y emite
    `element_selected(style_key)`; `set_zoom()`/`zoom()` controlan el
    acercamiento; `set_show_grid()` superpone una cuadrícula de
    referencia (guía visual de márgenes/alineación). El modelo sigue
    siendo el de "documento fluido" para todo elemento, con una única
    excepción a propósito: el logo puede arrastrarse libremente con el
    mouse a cualquier posición absoluta de la hoja (ver
    `_make_logo_movable`/`logo_overlay_block`) — ningún otro bloque lo
    admite."""

    element_selected = Signal(str)
    spacing_offset_changed = Signal(str, float)
    """Emitida tras un micro-ajuste por teclado (`style_key`, offset total
    acumulado en puntos) — la vista guarda este valor en su propio
    `TemplateConfig` sin volver a pedirle un `set_settings()` al lienzo
    (ya se movió solo, de forma incremental; ver `_apply_nudge`)."""
    logo_position_changed = Signal(float, float)
    """Emitida tras arrastrar o mover con las flechas el logo (x, y en
    puntos, posición absoluta) — mismo espíritu que `spacing_offset_changed`:
    el lienzo ya se movió solo, la vista solo necesita reflejarlo en su
    propio `TemplateConfig` y en el panel de propiedades."""
    logo_double_clicked = Signal()
    """Doble clic sobre el logo — la vista la conecta directamente al
    mismo manejador que ya abre el selector de archivo del botón
    "Seleccionar logo", sin lógica de diálogo nueva."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMinimumSize(260, 340)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._settings = InvoiceSettingsDTO()
        self._pending_settings = self._settings
        self._plan: LayoutPlan = build_layout_plan(self._settings, _SAMPLE_RENDER_DATA)
        self._zoom = 1.0
        self._show_grid = False
        self._block_items: list[list[_BlockGraphicsItem]] = []
        self._current_block_items: list[_BlockGraphicsItem] = []
        self._content_bottom_pt = 0.0
        self._selected_style_key: str | None = None
        self._logo_overlay_item: _BlockGraphicsItem | None = None

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self._rebuild_scene)

        self._rebuild_scene()
        self._scene.selectionChanged.connect(self._on_selection_changed)

    # -- API pública ----------------------------------------------------

    def set_settings(self, settings: InvoiceSettingsDTO) -> None:
        self._pending_settings = settings
        self._debounce.start()

    def current_layout_plan(self) -> LayoutPlan:
        """Expuesto para pruebas — el plano vigente en pantalla."""
        return self._plan

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, zoom))
        self.resetTransform()
        self.scale(self._zoom, self._zoom)

    def zoom(self) -> float:
        return self._zoom

    def set_show_grid(self, show_grid: bool) -> None:
        self._show_grid = show_grid
        self._scene.update()

    # -- construcción de la escena ---------------------------------------

    def _rebuild_scene(self) -> None:
        self._settings = self._pending_settings
        self._plan = build_layout_plan(self._settings, _SAMPLE_RENDER_DATA)
        self._scene.clear()

        page = self._plan.page
        page_w_pt = max(page.width_mm, 1.0) * PT_PER_MM
        page_h_pt = max(page.height_mm, 1.0) * PT_PER_MM
        self._scene.setSceneRect(-20, -20, page_w_pt + 40, page_h_pt + 40)

        page_item = self._scene.addRect(
            QRectF(0, 0, page_w_pt, page_h_pt), QPen(QColor("#CCCCCC")), QColor("white")
        )
        page_item.setZValue(-1)

        margin_left_pt = page.margin_left_mm * PT_PER_MM
        margin_right_pt = page.margin_right_mm * PT_PER_MM
        margin_top_pt = page.margin_top_mm * PT_PER_MM
        content_width_pt = max(page_w_pt - margin_left_pt - margin_right_pt, 1.0)

        y = margin_top_pt
        base_pt = page.base_font_size_pt
        self._block_items = []
        for block in self._plan.blocks:
            self._current_block_items = []
            y = self._add_block_item(block, content_width_pt, y, base_pt, margin_left_pt)
            self._block_items.append(self._current_block_items)
        self._content_bottom_pt = y

        self._logo_overlay_item = None
        logo_overlay = logo_overlay_block(self._settings)
        if logo_overlay is not None:
            self._add_logo_overlay_item(logo_overlay)

        if self._selected_style_key is not None:
            self._reselect(self._selected_style_key)

    def _register_item(self, item: _BlockGraphicsItem) -> None:
        self._scene.addItem(item)
        self._current_block_items.append(item)

    def _reselect(self, style_key: str) -> None:
        """Tras una reconstrucción completa de la escena (`_scene.clear()`
        destruye todos los items previos), vuelve a marcar como
        seleccionado el bloque que lo estaba antes — sin esto, cada ajuste
        de propiedades (o el primer micro-ajuste por teclado sobre un
        elemento nuevo, ver `_apply_nudge`) haría que la selección
        desapareciera del lienzo."""
        for items in self._block_items:
            for item in items:
                if item.style_key == style_key:
                    item.setSelected(True)
                    return
        if self._logo_overlay_item is not None and self._logo_overlay_item.style_key == style_key:
            self._logo_overlay_item.setSelected(True)

    def _add_block_item(
        self, block: Block, width: float, y: float, base_pt: int, x_offset: float
    ) -> float:
        if isinstance(block, TextBlock):
            return self._add_text_item(block, width, y, base_pt, x_offset)
        if isinstance(block, SpacerBlock):
            return y + block.height_pt
        if isinstance(block, ImageBlock):
            return self._add_image_item(block, y, x_offset, width)
        if isinstance(block, QrBlock):
            return self._add_qr_item(block, y, x_offset, width)
        if isinstance(block, BarcodeBlock):
            return self._add_barcode_item(block, y, x_offset, width)
        if isinstance(block, TableBlock):
            return self._add_table_item(block, width, y, base_pt, x_offset)
        return y

    def _add_text_item(
        self, block: TextBlock, width: float, y: float, base_pt: int, x_offset: float
    ) -> float:
        measured = build_text_block(block, width, base_pt)
        rect = QRectF(0, 0, measured.width, measured.height)
        top = y + measured.space_before
        item = _BlockGraphicsItem(rect, block.style_key, measured.paint)
        item.setPos(x_offset, top)
        self._register_item(item)
        return top + measured.height

    def _add_image_item(
        self, block: ImageBlock, y: float, x_offset: float, available_width: float
    ) -> float:
        measured = build_image_block(
            block.path, block.image_style, block.max_width_pt, block.max_height_pt, block.style_key
        )
        if measured is None:
            return y
        rect = QRectF(0, 0, measured.width, measured.height)
        x = aligned_x(measured.width, available_width, block.image_style.align)
        item = _BlockGraphicsItem(rect, block.style_key, measured.paint)
        item.setPos(x_offset + x, y)
        if block.style_key == "logo":
            self._make_logo_movable(item)
        self._register_item(item)
        return y + measured.height + measured.gap_after

    def _make_logo_movable(self, item: _BlockGraphicsItem) -> None:
        """Solo el logo recibe esto — ningún otro tipo de bloque llama a
        este método. `clamp_position=True` en `_BlockGraphicsItem` ya
        evita coordenadas negativas (ver `itemChange`); acá solo se
        agrega el flag de arrastre y se conectan los callbacks."""
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        item._clamp_position = True  # noqa: SLF001 (mismo objeto, sin setter público)
        item._on_moved = lambda pos, target=item: self._on_logo_item_moved(target, pos)  # noqa: SLF001
        item._on_double_click = self.logo_double_clicked.emit  # noqa: SLF001

    def _on_logo_item_moved(self, item: _BlockGraphicsItem, new_pos: QPointF) -> None:
        """El item ya se movió solo (arrastre nativo de Qt, o
        `item.setPos()` desde `_nudge_logo`) — acá solo se sincroniza el
        estado interno y se avisa a la vista, sin reconstruir la escena.
        Se ejecuta igual la primera vez (el logo pasa de estar en flujo a
        superposición absoluta, sin ningún salto visual porque el item
        nunca se recreó) que en los movimientos siguientes."""
        item.setZValue(_LOGO_OVERLAY_Z_VALUE)
        self._logo_overlay_item = item

        logo_style = self._settings.template.image_styles.get("logo", ImageStyle())
        new_style = replace(logo_style, absolute_x_pt=new_pos.x(), absolute_y_pt=new_pos.y())
        new_image_styles = {**self._settings.template.image_styles, "logo": new_style}
        new_template = replace(self._settings.template, image_styles=new_image_styles)
        new_settings = replace(self._settings, template=new_template)
        self._settings = new_settings
        self._pending_settings = new_settings

        self.logo_position_changed.emit(new_pos.x(), new_pos.y())

    def _add_logo_overlay_item(self, block: ImageBlock) -> None:
        measured = build_image_block(
            block.path, block.image_style, block.max_width_pt, block.max_height_pt, block.style_key
        )
        if measured is None:
            return
        rect = QRectF(0, 0, measured.width, measured.height)
        item = _BlockGraphicsItem(rect, block.style_key, measured.paint)
        item.setPos(block.image_style.absolute_x_pt, block.image_style.absolute_y_pt)
        item.setZValue(_LOGO_OVERLAY_Z_VALUE)
        self._make_logo_movable(item)
        self._scene.addItem(item)
        self._logo_overlay_item = item

    def _add_qr_item(
        self, block: QrBlock, y: float, x_offset: float, available_width: float
    ) -> float:
        measured = build_qr_block(block)
        rect = QRectF(0, 0, measured.width, measured.height)
        x = aligned_x(measured.width, available_width, block.image_style.align)
        item = _BlockGraphicsItem(rect, block.style_key, measured.paint)
        item.setPos(x_offset + x, y)
        self._register_item(item)
        return y + measured.height + measured.gap_after

    def _add_barcode_item(
        self, block: BarcodeBlock, y: float, x_offset: float, available_width: float
    ) -> float:
        measured = build_barcode_block(block)
        if measured is None:
            return y
        rect = QRectF(0, 0, measured.width, measured.height)
        x = aligned_x(measured.width, available_width, block.image_style.align)
        item = _BlockGraphicsItem(rect, block.style_key, measured.paint)
        item.setPos(x_offset + x, y)
        self._register_item(item)
        return y + measured.height + measured.gap_after

    def _add_table_item(
        self, block: TableBlock, width: float, y: float, base_pt: int, x_offset: float
    ) -> float:
        top = y
        for measured in build_table_rows(block, width, base_pt):
            rect = QRectF(0, 0, measured.width, measured.height)
            item = _BlockGraphicsItem(rect, block.style_key, measured.paint)
            item.setPos(x_offset, top)
            self._register_item(item)
            top += measured.height
        return top + BLOCK_GAP_AFTER_PT

    # -- selección / cuadrícula ------------------------------------------

    def _on_selection_changed(self) -> None:
        selected = self._scene.selectedItems()
        if selected and isinstance(selected[0], _BlockGraphicsItem):
            self._selected_style_key = selected[0].style_key
            self.element_selected.emit(selected[0].style_key)

    # -- micro-posicionamiento por teclado --------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        # Rama exclusiva del logo — se revisa ANTES que la lógica de
        # siempre (Arriba/Abajo únicamente, para el resto de los
        # elementos) y no la modifica en absoluto: si no se cumple esta
        # condición, el código de abajo sigue exactamente igual.
        selected = self._scene.selectedItems()
        if (
            selected
            and isinstance(selected[0], _BlockGraphicsItem)
            and selected[0].style_key == "logo"
            and event.key() in _LOGO_ARROW_KEYS
        ):
            self._nudge_logo(selected[0], event.key(), event.modifiers())
            event.accept()
            return

        if event.key() not in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            super().keyPressEvent(event)
            return
        if not selected or not isinstance(selected[0], _BlockGraphicsItem):
            super().keyPressEvent(event)
            return
        # Auto-repeat de Qt/SO se deja pasar sin filtrar (no se descarta
        # `event.isAutoRepeat()`) — mantener presionada la flecha se mueve
        # de forma continua, igual que en un procesador de texto.
        steps = _step_count(event.modifiers())
        direction = -1.0 if event.key() == Qt.Key.Key_Up else 1.0
        self._apply_nudge(selected[0].style_key, direction * steps * NUDGE_STEP_PT)
        event.accept()

    def _nudge_logo(
        self, item: _BlockGraphicsItem, key: Qt.Key, modifiers: Qt.KeyboardModifier
    ) -> None:
        """Complementa (no reemplaza) el arrastre con mouse — mismo canal
        de salida (`item.setPos()` → `itemChange` → clamp → `_on_logo_item_moved`),
        así que el resultado es idéntico sin importar cómo se movió."""
        step = _logo_step_count(modifiers)
        dx = -step if key == Qt.Key.Key_Left else (step if key == Qt.Key.Key_Right else 0.0)
        dy = -step if key == Qt.Key.Key_Up else (step if key == Qt.Key.Key_Down else 0.0)
        item.setPos(item.pos() + QPointF(dx, dy))

    def _page_bottom_pt(self) -> float:
        page = self._plan.page
        page_h_pt = max(page.height_mm, 1.0) * PT_PER_MM
        return page_h_pt - page.margin_bottom_mm * PT_PER_MM

    def _first_block_index(self, style_key: str) -> int | None:
        return next(
            (i for i, block in enumerate(self._plan.blocks)
             if getattr(block, "style_key", None) == style_key),
            None,
        )

    def _has_leading_spacer(self, style_key: str) -> bool:
        index = self._first_block_index(style_key)
        if index is None or index == 0:
            return False
        return isinstance(self._plan.blocks[index - 1], SpacerBlock)

    def _apply_nudge(self, style_key: str, delta_pt: float) -> None:
        # El límite inferior (nunca superposición/espacio negativo) ya lo
        # garantiza `_apply_spacing_offsets` en el dominio (el hueco nunca
        # baja de 0). Acá solo hace falta el límite superior — que un
        # bloque empujado hacia abajo no se salga de la página — porque es
        # el único lugar que ya tiene la posición acumulada real.
        if delta_pt > 0:
            available = max(self._page_bottom_pt() - self._content_bottom_pt, 0.0)
            delta_pt = min(delta_pt, available)
        if delta_pt == 0:
            return

        current_offset = self._settings.template.spacing_offsets.get(style_key, 0.0)
        new_offset = current_offset + delta_pt
        new_offsets = {**self._settings.template.spacing_offsets, style_key: new_offset}
        new_template = replace(self._settings.template, spacing_offsets=new_offsets)
        new_settings = replace(self._settings, template=new_template)

        if self._has_leading_spacer(style_key):
            # Camino rápido: el hueco ya existe, solo cambia de alto — la
            # cantidad de bloques/items no cambia, así que basta con
            # reposicionar los items existentes desde acá en adelante, sin
            # reconstruir el resto de la escena. El corrimiento real se
            # calcula del antes/después del propio `SpacerBlock` (no de
            # `delta_pt` a secas) porque el piso en 0 puede haber
            # absorbido parte o todo el pedido — así el lienzo nunca
            # queda visualmente desincronizado del `LayoutPlan` real.
            index = self._first_block_index(style_key)
            old_height = self._plan.blocks[index - 1].height_pt
            new_plan = build_layout_plan(new_settings, _SAMPLE_RENDER_DATA)
            new_height = new_plan.blocks[index - 1].height_pt
            actual_shift = new_height - old_height

            self._settings = new_settings
            self._pending_settings = new_settings
            self._plan = new_plan
            if actual_shift:
                for items in self._block_items[index:]:
                    for item in items:
                        pos = item.pos()
                        item.setPos(pos.x(), pos.y() + actual_shift)
            self._content_bottom_pt += actual_shift
        else:
            # Primer micro-ajuste sobre este elemento: hay que insertar un
            # hueco nuevo (cambia la cantidad de bloques), así que esta
            # vez sí hace falta una reconstrucción completa. Los ajustes
            # siguientes sobre el mismo elemento ya entran por el camino
            # rápido de arriba.
            self._pending_settings = new_settings
            self._debounce.stop()
            self._rebuild_scene()

        self.spacing_offset_changed.emit(style_key, new_offset)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        if not self._show_grid:
            return
        painter.setPen(_GRID_GUIDE_PEN)
        left = int(rect.left()) - (int(rect.left()) % int(_GRID_STEP_PT))
        top = int(rect.top()) - (int(rect.top()) % int(_GRID_STEP_PT))
        x = left
        while x < rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += _GRID_STEP_PT
        y = top
        while y < rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += _GRID_STEP_PT
