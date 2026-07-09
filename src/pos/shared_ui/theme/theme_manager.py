"""Generación de QSS a partir de tokens de diseño y aplicación a la app.

La persistencia del tema activo (tabla `themes_config`) y la UI para
personalizar colores/logo son responsabilidad del módulo `settings`
(panel de administración); este gestor solo sabe convertir tokens en QSS
y aplicarlos — no conoce la base de datos.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from pos.shared_ui.theme.tokens import DARK_THEME, LIGHT_THEME, ThemeTokens

_QSS_TEMPLATE = """
QWidget {{
    background-color: {background};
    color: {text_primary};
    font-family: {font_family};
    font-size: {font_size_pt}pt;
}}

QMainWindow, QDialog {{
    background-color: {background};
}}

QFrame#surface, QGroupBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {radius_px}px;
}}

QPushButton {{
    background-color: {primary};
    color: {on_primary};
    border: none;
    border-radius: {radius_px}px;
    min-height: {touch_control_min_height_px}px;
    padding: 6px 16px;
}}

QPushButton:disabled {{
    background-color: {border};
    color: {text_secondary};
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {surface};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: {radius_px}px;
    min-height: {touch_control_min_height_px}px;
    padding: 2px 8px;
}}

QLabel[role="secondary"] {{
    color: {text_secondary};
}}

QLabel[role="danger"] {{
    color: {danger};
}}

QLabel[role="success"] {{
    color: {success};
}}
"""


def generate_qss(tokens: ThemeTokens) -> str:
    """Genera el stylesheet Qt (QSS) correspondiente a un conjunto de tokens."""
    return _QSS_TEMPLATE.format(**tokens.__dict__)


class ThemeManager:
    """Aplica un `ThemeTokens` a la `QApplication` activa."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._active: ThemeTokens = LIGHT_THEME

    @property
    def active(self) -> ThemeTokens:
        """Tokens del tema actualmente aplicado."""
        return self._active

    def apply(self, tokens: ThemeTokens) -> None:
        """Aplica el tema `tokens` a toda la aplicación."""
        self._active = tokens
        self._app.setStyleSheet(generate_qss(tokens))

    def apply_light(self) -> None:
        """Aplica el tema claro por defecto."""
        self.apply(LIGHT_THEME)

    def apply_dark(self) -> None:
        """Aplica el tema oscuro por defecto."""
        self.apply(DARK_THEME)
