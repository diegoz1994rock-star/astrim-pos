"""Tokens de diseño (colores, radios, tipografía) de la identidad visual
"Cristal Oscuro" — ver DESIGN_SYSTEM.md. Ninguna pantalla debe tener colores
u estilos hardcodeados fuera de este módulo (ver ARCHITECTURE.md §7).

Existe un único tema (`DARK_THEME`) — el tema claro se eliminó porque la
identidad "cristal oscuro/glow" (bordes con brillo azul eléctrico, sombras
de profundidad) no tiene una traducción coherente sobre fondo blanco."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    """Conjunto completo de valores de diseño para un tema."""

    name: str
    background: str
    surface: str
    card_surface: str
    """Un nivel de profundidad por encima de `surface` — paneles/diálogos
    usan `surface`, las tarjetas que "flotan" sobre ellos (`KpiCard`,
    tarjeta de acceso rápido, filas de tabla, chips) usan `card_surface`.
    Antes ambas compartían `surface`; la referencia "Cristal Oscuro" pide
    un nivel más de jerarquía entre panel y tarjeta."""
    hover_surface: str
    """Fondo de hover de filas/tarjetas clicables — valor directo (no
    derivado de `primary`/`surface` vía `_blend`) porque la identidad
    "Cristal Oscuro" especifica un tono de hover exacto."""
    primary: str
    on_primary: str
    text_primary: str
    text_secondary: str
    border: str
    success: str
    warning: str
    danger: str
    header_accent: str
    """Fondo de encabezados de tabla (fila de títulos de columna y columna
    de números de fila), distinto del resto de la tabla para que se note
    a simple vista dónde termina el encabezado y empieza el contenido."""
    success_tint: str
    warning_tint: str
    danger_tint: str
    """Versión de fondo tenue de `success`/`warning`/`danger` — para
    resaltar una fila/celda completa (stock bajo, factura vencida, margen
    bajo) sin usar el color de texto de estado a pantalla completa. Ver
    DESIGN_SYSTEM.md §1.3 — reemplaza los colores hardcodeados que varios
    módulos definían por su cuenta (nunca reactivos al tema)."""
    radius_px: int = 12
    radius_sm_px: int = 6
    """Chips/badges y etiquetas pequeñas — ver DESIGN_SYSTEM.md §4."""
    radius_lg_px: int = 16
    """Superficies grandes elevadas: diálogos, panel de bienvenida — ver
    DESIGN_SYSTEM.md §4."""
    font_family: str = (
        "Nunito, Segoe UI, SF Pro Text, Helvetica Neue, Ubuntu, Noto Sans, sans-serif"
    )
    """Nunito (empaquetada, licencia OFL — ver `resources/fonts/OFL.txt` y
    `shared_ui/theme/fonts.py::load_bundled_fonts`) primero; si por algún
    motivo no cargó, Qt cae en cascada a la pila de fuentes nativas del
    sistema operativo — nunca un fallo duro. Reemplaza la pila 100%
    dependiente del SO usada antes de la identidad "Cristal Oscuro" — ver
    DESIGN_SYSTEM.md §2."""
    font_size_pt: int = 13
    caption_font_size_pt: int = 11
    """Texto auxiliar/metadatos (ej. "Última actualización hace 2 min") —
    un escalón por debajo del cuerpo normal, para separarlo visualmente sin
    depender solo de `role="secondary"` (color) para dar esa jerarquía."""
    title_font_size_pt: int = 16
    """Tamaño de los títulos de sección/pestaña — más grande que el texto
    normal para que resalten (ver `QLabel[role="title"]`, `QTabBar::tab`)."""
    amount_font_size_pt: int = 28
    """Tamaño del total de venta en los modales de cobro manual (QR/Nequi/
    Bre-B, ver `shared_ui/widgets/manual_payment_dialog.py`)."""
    hero_font_size_pt: int = 72
    """Tamaño del elemento central de un modal de cobro manual (número de
    Nequi / llave Bre-B) — el texto más grande de toda la app, pensado
    para leerse a distancia."""
    status_font_size_pt: int = 22
    """Tamaño de un estado destacado dentro de una fila/tarjeta compacta
    (ej. PENDIENTE/EN PREPARACIÓN/ENTREGADO en Despacho) — más grande que
    `title_font_size_pt` pero mucho menor que `hero_font_size_pt` (ese es
    para un modal a pantalla completa, esto vive dentro de una fila junto
    a más contenido). Propiedad `sizeVariant`, no `size` (colisiona con la
    property Qt real del mismo nombre — el tamaño del widget — y nunca
    matchea) ni `role` — así una etiqueta puede combinar tamaño
    (`sizeVariant="status"`) con color semántico (`role="warning"
    |"info"|"success"`) al mismo tiempo, algo que `role="hero"`/`"amount"`
    no permiten por sí solos."""
    touch_control_min_height_px: int = 52
    """Alto mínimo de controles interactivos, pensado para pantallas táctiles."""


DARK_THEME = ThemeTokens(
    name="dark",
    background="#111C2F",
    surface="#16233B",
    card_surface="#1B2C49",
    hover_surface="#233A5D",
    primary="#3B82F6",
    on_primary="#FFFFFF",
    text_primary="#EAF1FB",
    text_secondary="#8CA0C4",
    border="#2A3F63",
    success="#34D399",
    warning="#FBBF24",
    danger="#F87171",
    header_accent="#20315A",
    success_tint="#173B2C",
    warning_tint="#3D2F14",
    danger_tint="#3D2024",
)
