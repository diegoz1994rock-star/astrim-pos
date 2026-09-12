"""Iconografía oficial del sistema (ver DESIGN_SYSTEM.md §10).

Reemplaza el uso de emoji como ícono de navegación/identidad — antes: los
13 íconos de acceso rápido del Dashboard (`main.py::_PANEL_ICONS`) y la
campana/usuario de la barra superior. El emoji renderiza distinto entre
Windows/macOS/Linux (cada sistema operativo trae su propia fuente de
emoji, con estilo y color propios), lo que contradice tener un lenguaje
visual único — y su color no obedece al tema (siempre sale con el color
nativo del emoji, nunca el `text_primary`/`on_primary` que corresponde).

Cada ícono se define en `_SHAPES` como un fragmento SVG hecho *solo* de
formas primitivas (`rect`/`circle`/`line`/`polyline`/`polygon`) — nunca
curvas Bézier escritas a mano, para no arriesgar coordenadas mal
calculadas sin poder ver el resultado renderizado en este entorno. Se
colorea en tiempo de ejecución con el token que corresponda (`get_icon`),
así el mismo ícono se ve correcto en tema claro y oscuro."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

DEFAULT_ICON_SIZE = 20

_STROKE_WIDTH = 1.8

_SHAPES: dict[str, str] = {
    "settings": (
        '<line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2"/>'
        '<line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2"/>'
        '<line x1="4" y1="18" x2="20" y2="18"/><circle cx="11" cy="18" r="2"/>'
    ),
    "trending-up": (
        '<polyline points="3,17 9,11 13,15 21,6"/><polyline points="15,6 21,6 21,12"/>'
    ),
    "clipboard": (
        '<rect x="5" y="4" width="14" height="17" rx="2"/>'
        '<rect x="9" y="2" width="6" height="3" rx="1"/>'
        '<line x1="8" y1="11" x2="16" y2="11"/><line x1="8" y1="15" x2="16" y2="15"/>'
    ),
    "receipt": (
        '<rect x="6" y="3" width="12" height="18"/>'
        '<line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="15" y2="11"/>'
        '<line x1="9" y1="15" x2="13" y2="15"/>'
    ),
    "package": (
        '<polygon points="12,3 21,8 21,16 12,21 3,16 3,8"/>'
        '<line x1="12" y1="21" x2="12" y2="12"/>'
        '<line x1="3" y1="8" x2="12" y2="12"/><line x1="21" y1="8" x2="12" y2="12"/>'
    ),
    "users": (
        '<circle cx="9" cy="7" r="3"/><polygon points="4,21 5,15 13,15 14,21"/>'
        '<circle cx="17" cy="9" r="2.2"/><polygon points="15,21 15.5,17 21,17 21.5,21"/>'
    ),
    "cash": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="3"/>',
    "cart": (
        '<polyline points="3,4 5,4 8,15 18,15 20,7 7,7"/>'
        '<circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>'
    ),
    "bar-chart": (
        '<rect x="4" y="12" width="4" height="9"/><rect x="10" y="6" width="4" height="15"/>'
        '<rect x="16" y="15" width="4" height="6"/>'
    ),
    "key": (
        '<circle cx="6" cy="12" r="4"/><line x1="10" y1="12" x2="21" y2="12"/>'
        '<line x1="17" y1="12" x2="17" y2="16"/><line x1="20" y1="12" x2="20" y2="15"/>'
    ),
    "save": (
        '<rect x="4" y="4" width="16" height="16" rx="1"/>'
        '<rect x="8" y="4" width="8" height="5"/><rect x="7" y="14" width="10" height="6"/>'
    ),
    "sync": (
        '<polyline points="3,8 3,5 21,5"/><polyline points="18,2 21,5 18,8"/>'
        '<polyline points="21,16 21,19 3,19"/><polyline points="6,22 3,19 6,16"/>'
    ),
    "bell": (
        '<polygon points="12,3 10,3.5 8,6 7,10 6,14 18,14 17,10 16,6 14,3.5"/>'
        '<line x1="5" y1="14" x2="19" y2="14"/><circle cx="12" cy="17.5" r="1.3"/>'
    ),
    "user": '<circle cx="12" cy="8" r="4"/><polygon points="5,21 6,15 18,15 19,21"/>',
    "square": '<rect x="7" y="7" width="10" height="10" rx="1"/>',
    "wallet": (
        '<rect x="3" y="6" width="18" height="13" rx="2"/>'
        '<line x1="3" y1="10" x2="21" y2="10"/><circle cx="17" cy="13.5" r="1.3"/>'
    ),
    "basket": (
        '<polygon points="4,10 20,10 18,20 6,20"/>'
        '<polyline points="7,10 7.5,5.5 9.5,3.5 14.5,3.5 16.5,5.5 17,10"/>'
        '<line x1="9" y1="13" x2="10" y2="18"/><line x1="15" y1="13" x2="14" y2="18"/>'
    ),
    "chevron-right": '<polyline points="9,4 16,12 9,20"/>',
    "play": '<polygon points="7,4 20,12 7,20"/>',
    "stop": '<rect x="6" y="6" width="12" height="12"/>',
    "copy": (
        '<rect x="9" y="9" width="11" height="11" rx="1"/>'
        '<rect x="4" y="4" width="11" height="11" rx="1"/>'
    ),
    "search": '<circle cx="10" cy="10" r="6"/><line x1="14.5" y1="14.5" x2="20" y2="20"/>',
}
"""Un ícono por concepto de navegación real de la app — no un set
genérico. `"square"` es el respaldo explícito para un `label` sin ícono
mapeado (ver `main.py::_DEFAULT_PANEL_ICON`, antes `"▫️"`)."""

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
    'stroke-linecap="round" stroke-linejoin="round">{shape}</svg>'
)


def get_icon(name: str, color: str, size: int = DEFAULT_ICON_SIZE) -> QIcon:
    """Renderiza el ícono `name` (ver `_SHAPES`, cae a `"square"` si no
    existe) coloreado con `color` (un hex de `ThemeTokens`, ej.
    `tokens.on_primary` sobre un botón primario, `tokens.text_primary`
    sobre una superficie plana) al tamaño `size` en píxeles. Qt no tiene
    equivalente a `currentColor` de CSS — el color se hornea en el
    fragmento SVG antes de rasterizarlo, así que un ícono nuevo por color
    se genera en cada llamada (no hay caché: el costo es insignificante
    frente al de reconstruir el widget que lo usa)."""
    shape = _SHAPES.get(name, _SHAPES["square"])
    svg = _SVG_TEMPLATE.format(color=color, stroke_width=_STROKE_WIDTH, shape=shape)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
