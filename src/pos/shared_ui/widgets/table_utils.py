"""Utilidades compartidas de tablas/listas: que una `QTableWidget`/
`QListWidget` crezca con su contenido en vez de mostrar su propia barra
de scroll interna (el único desplazamiento queda a cargo del
`QScrollArea` de página de cada pantalla, ver
`shared_ui/widgets/scrollable_page.py`), y una celda de imagen de
producto consistente en toda la app (Vendedor, Despacho, Catálogo,
Inventario)."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTableWidget,
    QWidget,
)

from pos.shared_ui.theme.theme_manager import get_active_tokens

STATUS_ROLE_ROLE = Qt.ItemDataRole.UserRole + 2
"""Rol de dato custom que expone el `role` semántico ("success"|"warning"|
"danger"|"secondary") de una celda de estado para `StatusChipDelegate` —
`Qt.ItemDataRole.UserRole + 1` ya está tomado por `SEARCH_ROLE` (ver
`search_filter_proxy_model.py`)."""


def fit_table_view_to_contents(table: QTableView) -> None:
    """Igual que `fit_table_to_contents` pero para `QTableView` (modelo +
    `QSortFilterProxyModel`, ver `products_table_model.py`/
    `inventory_table_model.py`) — usa `model().rowCount()` en vez de
    `table.rowCount()` (que no existe en `QTableView`), así que ya refleja
    la cantidad de filas después de filtrar por el buscador."""
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    header = table.horizontalHeader()
    row_height = table.verticalHeader().defaultSectionSize()
    model = table.model()
    row_count = model.rowCount() if model is not None else 0
    total_height = header.height() + row_height * max(row_count, 1) + 2 * table.frameWidth()
    table.setFixedHeight(total_height)


def fit_table_to_contents(table: QTableWidget) -> None:
    """Apaga la barra de scroll vertical de `table` y fija su altura para
    mostrar todas las filas actuales sin recortar. Se llama después de
    poblar filas (`setRowCount` + `setItem`/`setCellWidget`), cada vez que
    cambian."""
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    header = table.horizontalHeader()
    row_height = table.verticalHeader().defaultSectionSize()
    total_height = (
        header.height() + row_height * max(table.rowCount(), 1) + 2 * table.frameWidth()
    )
    table.setFixedHeight(total_height)


def fit_list_to_contents(list_widget: QListWidget, *, minimum_rows: int = 1) -> None:
    """Igual que `fit_table_to_contents` pero para `QListWidget` — apaga
    su barra de scroll vertical propia y fija su altura para mostrar
    todos sus ítems actuales sin recortar. Se llama después de poblar
    ítems, cada vez que cambian. `minimum_rows` evita que una lista vacía
    quede con alto cero (se ve como si el panel hubiera desaparecido)."""
    list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    row_height = list_widget.sizeHintForRow(0) if list_widget.count() else -1
    if row_height <= 0:
        row_height = list_widget.fontMetrics().height() + 8
    visible_rows = max(list_widget.count(), minimum_rows)
    total_height = row_height * visible_rows + 2 * list_widget.frameWidth()
    list_widget.setFixedHeight(total_height)


def make_image_cell(
    image_path: str | None, size: int, placeholder_point_size: int = 20
) -> QLabel:
    """`QLabel` centrado con la imagen del producto escalada a `size`, o
    un ícono "imagen no disponible" (glifo, sin assets nuevos) si el
    producto no tiene ninguna."""
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = QPixmap(image_path) if image_path else QPixmap()
    if not pixmap.isNull():
        label.setPixmap(
            pixmap.scaled(
                size,
                size,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
        )
    else:
        label.setText("🖼️")
        font = QFont()
        font.setPointSize(placeholder_point_size)
        label.setFont(font)
    return label


def make_image_icon(image_path: str | None, size: int) -> QIcon:
    """Igual que `make_image_cell` pero como `QIcon` para
    `Qt.ItemDataRole.DecorationRole` de un `QAbstractTableModel` —
    incluyendo el mismo placeholder "🖼️" (rasterizado a un `QPixmap`, ya
    que un ícono de celda no admite un `QLabel` de texto) cuando el
    producto no tiene imagen, para que la columna se vea igual que con
    `make_image_cell`."""
    pixmap = QPixmap(image_path) if image_path else QPixmap()
    if not pixmap.isNull():
        return QIcon(
            pixmap.scaled(
                size,
                size,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
        )
    placeholder = QPixmap(size, size)
    placeholder.fill(Qt.GlobalColor.transparent)
    painter = QPainter(placeholder)
    font = QFont()
    font.setPointSize(size // 3)
    painter.setFont(font)
    painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, "🖼️")
    painter.end()
    return QIcon(placeholder)


DEFAULT_IMAGE_CELL_SIZE = 100
DEFAULT_IMAGE_CELL_MARGIN = 5


class ImageCellDelegate(QStyledItemDelegate):
    """Pinta a mano la miniatura de un `Qt.ItemDataRole.DecorationRole`
    (un `QIcon`, ver `make_image_icon`) dentro de la celda — root cause
    de la regresión visual que este delegado corrige: por defecto, Qt
    dibuja cualquier ícono de `DecorationRole` al tamaño de
    `QAbstractItemView.iconSize()` (16x16 salvo que se fije
    explícitamente), sin ninguna relación con la resolución real del
    `QPixmap` ya escalado que trae el `QIcon` — así que la miniatura se
    veía diminuta sin importar cuán ancha fuera la columna. Este delegado
    ignora `iconSize()` por completo: toma el pixmap en su resolución
    real (`icon.availableSizes()`) y lo reescala él mismo con
    `Qt.KeepAspectRatio`/`Qt.SmoothTransformation` al espacio disponible
    de la celda (menos `margin` de cada lado), así que siempre ocupa
    prácticamente toda la celda sin deformarse ni perder nitidez, sin
    importar el tamaño de columna/fila configurado."""

    def __init__(
        self,
        cell_size: int = DEFAULT_IMAGE_CELL_SIZE,
        margin: int = DEFAULT_IMAGE_CELL_MARGIN,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cell_size = cell_size
        self._margin = margin

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        # Copia de `option` sin ícono/texto: delega en el estilo activo
        # solo el fondo de selección/foco (misma apariencia que cualquier
        # otra celda seleccionada), y pinta el pixmap por su cuenta a
        # continuación — así nunca se dibuja el ícono dos veces ni al
        # tamaño por defecto de Qt.
        opt = QStyleOptionViewItem(option)
        opt.icon = QIcon()
        opt.text = ""
        style = option.widget.style() if option.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, option.widget)

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(icon, QIcon) or icon.isNull():
            return
        sizes = icon.availableSizes()
        pixmap = icon.pixmap(sizes[0]) if sizes else QPixmap()
        if pixmap.isNull():
            return

        available = option.rect.adjusted(
            self._margin, self._margin, -self._margin, -self._margin
        )
        scaled = pixmap.scaled(
            available.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = available.x() + (available.width() - scaled.width()) // 2
        y = available.y() + (available.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(self._cell_size, self._cell_size)


class StatusChipDelegate(QStyledItemDelegate):
    """Pinta el texto de `Qt.ItemDataRole.DisplayRole` como un chip relleno
    (mismo lenguaje visual que `StatusBadge`, ver DESIGN_SYSTEM.md §14),
    coloreado según `STATUS_ROLE_ROLE`. Existe porque `QTableView` (modelo +
    `QSortFilterProxyModel`, ver `products_table_model.py`/
    `inventory_table_model.py`) no admite `setCellWidget` como `QTableWidget`
    — un delegado es la forma correcta de pintar una celda personalizada
    que siga funcionando con orden/filtro en vivo."""

    _CHIP_PADDING_H = 10
    _CHIP_PADDING_V = 4

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        opt = QStyleOptionViewItem(option)
        opt.icon = QIcon()
        opt.text = ""
        style = option.widget.style() if option.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, option.widget)

        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return
        role = index.data(STATUS_ROLE_ROLE) or "secondary"
        tokens = get_active_tokens()
        bg_hex, fg_hex = {
            "success": (tokens.success_tint, tokens.success),
            "warning": (tokens.warning_tint, tokens.warning),
            "danger": (tokens.danger_tint, tokens.danger),
            "secondary": (tokens.header_accent, tokens.text_secondary),
        }[role]

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        text_width = painter.fontMetrics().horizontalAdvance(text)
        text_height = painter.fontMetrics().height()
        chip_width = text_width + 2 * self._CHIP_PADDING_H
        chip_height = text_height + 2 * self._CHIP_PADDING_V
        chip_rect = QRectF(
            option.rect.x() + (option.rect.width() - chip_width) / 2,
            option.rect.y() + (option.rect.height() - chip_height) / 2,
            chip_width,
            chip_height,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg_hex))
        painter.drawRoundedRect(chip_rect, tokens.radius_sm_px, tokens.radius_sm_px)
        painter.setPen(QColor(fg_hex))
        painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()
