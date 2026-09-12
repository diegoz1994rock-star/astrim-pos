"""Contenedor de scroll estándar de página completa — un único componente
reutilizado por toda pantalla de nivel superior de la app, para que el
comportamiento de desplazamiento sea idéntico en todos los módulos (nunca
más una pantalla con `QScrollArea` y otra sin, ni distintas políticas de
barra de scroll).

Barra vertical siempre visible (nunca aparece/desaparece según el
contenido — a diferencia del default de Qt `ScrollBarAsNeeded`, que es la
causa de que antes unas pantallas mostraran la barra y otras no, o que
apareciera/desapareciera al cambiar de tamaño). Barra horizontal siempre
oculta: el contenido se piensa para refluir en vertical (formularios,
tablas con columnas redimensionables), no para desplazarse
horizontalmente."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD


def build_scrollable_page(parent: QWidget | None = None) -> tuple[QScrollArea, QVBoxLayout]:
    """Crea el `QScrollArea` de página completa de esta app.

    Uso estándar en `_build_ui()` de cualquier vista:

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            scroll_area, layout = build_scrollable_page(self)
            outer.addWidget(scroll_area)
            layout.addWidget(...)  # el resto de la pantalla, sin cambios

    `layout` viene con el margen/espaciado oficial de página
    (`SPACING_LG`/`SPACING_MD`, ver `shared_ui/theme/spacing.py`) — antes
    de la Fase 3 del Design System no fijaba ninguno, así que cada pantalla
    heredaba el margen por defecto de Qt (variable según plataforma) o
    definía el suyo propio sin ningún patrón. Una pantalla puede seguir
    llamando `layout.setContentsMargins(...)`/`setSpacing(...)` después de
    este `return` si de verdad necesita otra cosa — este valor es el punto
    de partida correcto, no una regla imposible de cambiar.

    Para que una `QTableWidget`/`QListWidget` muestre todo su contenido en
    vez de tener su propio scroll interno (para que el único
    desplazamiento sea el de esta página), ver `fit_table_to_contents`/
    `fit_list_to_contents` en `table_utils.py`.
    """
    scroll_area = QScrollArea(parent)
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
    content_layout.setSpacing(SPACING_MD)
    scroll_area.setWidget(content)

    return scroll_area, content_layout
