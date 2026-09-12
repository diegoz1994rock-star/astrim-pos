"""Panel de accesos rápidos: tarjetas grandes (ícono + título + descripción
+ flecha) agrupadas por categoría, cada grupo con un encabezado y una regla
horizontal. No decide qué está visible ni qué hace cada tarjeta — solo
dibuja lo que ya le pasan filtrado (ver `main.py`, `_panel_visible`)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pos.shared_ui.icons import get_icon
from pos.shared_ui.theme.elevation import apply_shadow
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XS
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.icon_badge import build_icon_badge

_MAX_COLUMNS = 4


def _group_header(text: str, parent: QWidget) -> QWidget:
    """Etiqueta de categoría + regla horizontal que ocupa el resto del
    ancho — distinto de `QLabel[role="title"]` (fondo sólido, ya usado como
    título de pantalla en todos los módulos): acá se necesita un rótulo más
    liviano, propio de una lista de navegación agrupada."""
    header = QWidget(parent)
    layout = QHBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SPACING_SM)
    label = QLabel(text, header)
    label.setProperty("role", "secondary")
    label.setProperty("emphasis", True)
    layout.addWidget(label)
    rule = QFrame(header)
    rule.setFrameShape(QFrame.Shape.HLine)
    layout.addWidget(rule, stretch=1)
    return header


class _NavItemCard(QFrame):
    """Tarjeta clicable de acceso rápido — mismo patrón ya usado en
    `kitchen_view.py::_OrderCard` (`QFrame` + `PointingHandCursor` +
    `mousePressEvent`, en vez de `QPushButton`, porque el contenido es
    multilínea con layout propio: ícono + título + descripción + flecha)."""

    def __init__(
        self, icon: str, label: str, description: str, on_click: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_click = on_click
        self.setProperty("navItem", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        tokens = get_active_tokens()
        apply_shadow(self, "sm", glow_color=tokens.primary)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        layout.setSpacing(SPACING_MD)

        badge = build_icon_badge(icon, tokens.primary, tokens.header_accent, size=36, parent=self)
        layout.addWidget(badge)

        text_column = QVBoxLayout()
        text_column.setSpacing(SPACING_XS)
        title_label = QLabel(label, self)
        title_label.setProperty("emphasis", True)
        text_column.addWidget(title_label)
        if description:
            description_label = QLabel(description, self)
            description_label.setProperty("role", "secondary")
            text_column.addWidget(description_label)
        layout.addLayout(text_column, stretch=1)

        chevron = QLabel(self)
        chevron.setPixmap(get_icon("chevron-right", tokens.text_secondary, size=18).pixmap(18, 18))
        layout.addWidget(chevron)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 (nombre de Qt)
        self._on_click()
        super().mousePressEvent(event)


class QuickAccessPanel(QWidget):
    """`items` es una lista de `(icon, label, group, description, on_click)`
    ya filtrada por permisos — cada entrada se agrupa por `group` en el
    orden en que aparece por primera vez. `icon` es un nombre de
    `shared_ui/icons.py`."""

    def __init__(
        self,
        items: list[tuple[str, str, str, str, Callable[[], None]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        groups: dict[str, list[tuple[str, str, str, Callable[[], None]]]] = {}
        for icon, label, group, description, on_click in items:
            groups.setdefault(group, []).append((icon, label, description, on_click))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_LG)

        for group_name, group_items in groups.items():
            section = QVBoxLayout()
            section.setSpacing(SPACING_SM)
            section.addWidget(_group_header(group_name, self))

            grid = QGridLayout()
            grid.setSpacing(SPACING_SM)
            columns = min(len(group_items), _MAX_COLUMNS)
            for col in range(columns):
                grid.setColumnStretch(col, 1)
            for index, (icon, label, description, on_click) in enumerate(group_items):
                card = _NavItemCard(icon, label, description, on_click, self)
                grid.addWidget(card, index // columns, index % columns)
            section.addLayout(grid)
            layout.addLayout(section)
