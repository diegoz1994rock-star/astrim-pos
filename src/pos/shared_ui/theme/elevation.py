"""Escala oficial de elevación (ver DESIGN_SYSTEM.md §8).

Qt QSS no soporta `box-shadow` — cualquier sombra real necesita
`QGraphicsDropShadowEffect` aplicado por código, no una regla de
stylesheet. Antes de esta fase no existía ningún uso de este efecto en
todo el proyecto (verificado por búsqueda exhaustiva): toda "tarjeta" era
un rectángulo plano con borde de 1px, sin profundidad.

Se usa solo donde una superficie de verdad "flota" sobre el fondo (una
tarjeta de KPI, un diálogo) — nunca en contenido que vive plano en el
flujo de la pantalla (una tabla, un formulario largo), donde una sombra
sería ruido visual en vez de comunicar jerarquía."""

from __future__ import annotations

from typing import Literal

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

ElevationLevel = Literal["none", "sm", "lg"]

# (blur_radius_px, (offset_x_px, offset_y_px), opacidad_negro)
# "sm" — tarjetas dentro de una grilla (ej. `KpiCard`).
# "lg" — superficies modales: diálogos, menús desplegables.
_LEVELS: dict[str, tuple[int, tuple[int, int], float]] = {
    "sm": (12, (0, 2), 0.12),
    "lg": (24, (0, 8), 0.18),
}


_GLOW_OPACITY = 0.55
"""Opacidad del glow de color — mucho más marcada que la sombra neutra
(12-18%) porque acá el color mismo es el mensaje ("borde iluminado", no
solo profundidad); ver DESIGN_SYSTEM.md, identidad "Cristal Oscuro"."""


def apply_shadow(
    widget: QWidget, level: ElevationLevel, *, glow_color: str | None = None
) -> None:
    """Aplica (o quita, con `level="none"`) la sombra oficial del nivel
    indicado a `widget`. Reemplaza cualquier `QGraphicsEffect` que el
    widget ya tuviera — un widget solo puede tener un efecto gráfico a la
    vez en Qt, así que esta función es la única fuente de verdad de la
    sombra de cualquier superficie elevada.

    `glow_color` (hex) reemplaza el negro por ese color a mayor opacidad —
    el "glow" pedido para tarjetas/paneles elevados. Sin `glow_color` el
    comportamiento es idéntico al de siempre (sombra neutra), así que los
    usos existentes no cambian salvo que se les pase el parámetro nuevo."""
    if level == "none":
        widget.setGraphicsEffect(None)
        return
    blur_radius, (offset_x, offset_y), opacity = _LEVELS[level]
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(offset_x, offset_y)
    color = QColor(glow_color) if glow_color is not None else QColor(0, 0, 0)
    color.setAlphaF(_GLOW_OPACITY if glow_color is not None else opacity)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)
