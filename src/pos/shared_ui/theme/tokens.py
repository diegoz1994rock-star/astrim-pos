"""Tokens de diseño (colores, radios, tipografía) que definen cada tema.

Cambiar de tema es cambiar el `ThemeTokens` activo; ninguna pantalla debe
tener colores u estilos hardcodeados fuera de este módulo
(ver ARCHITECTURE.md §7).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    """Conjunto completo de valores de diseño para un tema."""

    name: str
    background: str
    surface: str
    primary: str
    on_primary: str
    text_primary: str
    text_secondary: str
    border: str
    success: str
    warning: str
    danger: str
    radius_px: int = 8
    font_family: str = "Segoe UI, Arial, sans-serif"
    font_size_pt: int = 11
    touch_control_min_height_px: int = 44
    """Alto mínimo de controles interactivos, pensado para pantallas táctiles."""


LIGHT_THEME = ThemeTokens(
    name="light",
    background="#F5F6F8",
    surface="#FFFFFF",
    primary="#2F6FED",
    on_primary="#FFFFFF",
    text_primary="#1A1D21",
    text_secondary="#5B6470",
    border="#DDE1E6",
    success="#1E9E5A",
    warning="#D98C1B",
    danger="#D64545",
)

DARK_THEME = ThemeTokens(
    name="dark",
    background="#15181C",
    surface="#1F2328",
    primary="#5B8DEF",
    on_primary="#0B0E11",
    text_primary="#F2F3F5",
    text_secondary="#A3ACB8",
    border="#2C3138",
    success="#3CC98A",
    warning="#E6A23C",
    danger="#E5686B",
)
