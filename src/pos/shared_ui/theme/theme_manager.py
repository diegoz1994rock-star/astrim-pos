"""Generación de QSS a partir de tokens de diseño y aplicación a la app.

La persistencia del tema activo (tabla `themes_config`) y la UI para
personalizar colores/logo son responsabilidad del módulo `settings`
(panel de administración); este gestor solo sabe convertir tokens en QSS
y aplicarlos — no conoce la base de datos.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from pos.shared_ui.theme.tokens import DARK_THEME, ThemeTokens


def _shade(hex_color: str, amount: float) -> str:
    """Oscurece (`amount` negativo) o aclara (`amount` positivo) un color
    hex en la fracción indicada de su rango hacia negro/blanco — deriva los
    estados hover/pressed de un color base sin declarar un token nuevo por
    cada combinación color×estado (ver DESIGN_SYSTEM.md §5.1). Si el color
    primario cambia, sus estados hover/pressed se mantienen
    proporcionalmente correctos sin tocar nada más."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    if amount >= 0:
        r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    else:
        r, g, b = (round(c * (1 + amount)) for c in (r, g, b))
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def _blend(fg_hex: str, bg_hex: str, alpha: float) -> str:
    """Mezcla `fg_hex` sobre `bg_hex` a `alpha` de opacidad — usado para el
    hover de fila de tabla (`primary` al 8% sobre `surface`, ver
    DESIGN_SYSTEM.md §7), sin depender de `rgba()` en QSS (Qt lo soporta
    pero solo si el widget no define ya un `background-color` sólido más
    abajo en la cascada, lo que sí ocurre acá) ni de un token estático que
    quedaría desincronizado si `primary`/`surface` cambian."""
    fg_hex, bg_hex = fg_hex.lstrip("#"), bg_hex.lstrip("#")
    fg = (int(fg_hex[i : i + 2], 16) for i in (0, 2, 4))
    bg = (int(bg_hex[i : i + 2], 16) for i in (0, 2, 4))
    mixed = (round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg, strict=True))
    return f"#{'{:02X}{:02X}{:02X}'.format(*mixed)}"

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

QAbstractScrollArea, QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
    background-color: {background};
}}

QScrollArea {{
    border: none;
}}

QLabel {{
    background-color: transparent;
}}

QFrame#surface {{
    background-color: {card_surface};
    border: 1px solid {border};
    border-radius: {radius_px}px;
}}

QFrame#surface[selected="true"] {{
    border: 2px solid {primary};
}}

QFrame#surface[accent="primary"] {{
    border: 1px solid {accent_border_primary};
}}

QFrame#surface[accent="success"] {{
    border: 1px solid {accent_border_success};
}}

QFrame#surface[accent="secondary"] {{
    border: 1px solid {accent_border_secondary};
}}

QFrame[navItem="true"] {{
    background-color: {card_surface};
    border: 1px solid {border};
    border-radius: {radius_px}px;
}}

QFrame[navItem="true"]:hover {{
    background-color: {hover_surface};
    border: 1px solid {accent_border_primary};
}}

QGroupBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {radius_px}px;
    margin-top: 14px;
    padding-top: 10px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {text_primary};
    font-size: {title_font_size_pt}pt;
    font-weight: bold;
}}

QPushButton {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {primary}, stop:1 {primary_gradient_end});
    color: {on_primary};
    border: 2px solid transparent;
    border-radius: {radius_px}px;
    min-height: {touch_control_min_height_px}px;
    padding: 10px 20px;
}}

QPushButton:hover {{
    background-color: {primary_hover};
}}

QPushButton:pressed, QPushButton[active="true"] {{
    background-color: {primary_pressed};
}}

QPushButton:focus {{
    border: 2px solid {primary};
}}

QPushButton:disabled {{
    background-color: {border};
    color: {text_secondary};
    border-color: transparent;
}}

QPushButton[role="secondary"] {{
    background-color: {surface};
    color: {text_primary};
    border: 2px solid {border};
}}

QPushButton[role="secondary"]:hover {{
    border-color: {text_secondary};
}}

QPushButton[role="secondary"]:pressed, QPushButton[role="secondary"][active="true"] {{
    background-color: {border};
}}

QPushButton[role="secondary"]:focus {{
    border-color: {primary};
}}

QPushButton[role="secondary"]:disabled {{
    background-color: {surface};
    color: {text_secondary};
    border-color: {border};
}}

QPushButton[role="danger"] {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {danger}, stop:1 {danger_gradient_end});
    color: {on_primary};
}}

QPushButton[role="danger"]:hover {{
    background-color: {danger_hover};
}}

QPushButton[role="danger"]:pressed, QPushButton[role="danger"][active="true"] {{
    background-color: {danger_pressed};
}}

QPushButton[role="danger"]:focus {{
    border: 2px solid {danger};
}}

QPushButton[role="ghost"] {{
    background-color: transparent;
    color: {primary};
    border: 2px solid transparent;
    padding: 10px 14px;
}}

QPushButton[role="ghost"]:hover {{
    background-color: {border};
}}

QPushButton[role="ghost"]:pressed, QPushButton[role="ghost"][active="true"] {{
    background-color: {text_secondary};
    color: {surface};
}}

QPushButton[role="ghost"]:disabled {{
    background-color: transparent;
    color: {text_secondary};
}}

QPushButton[role="compact"] {{
    min-height: 36px;
    padding: 6px 14px;
}}

QPushButton[size="hero"] {{
    min-height: 64px;
    font-size: {title_font_size_pt}pt;
    font-weight: bold;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QDateEdit, QDateTimeEdit, QTextEdit, QPlainTextEdit {{
    background-color: {surface};
    color: {text_primary};
    border: 2px solid {border};
    border-radius: {radius_px}px;
    min-height: {touch_control_min_height_px}px;
    padding: 6px 12px;
}}

QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QDateEdit:hover, QDateTimeEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border-color: {text_secondary};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QDateTimeEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {primary};
}}

QLineEdit[state="error"], QComboBox[state="error"], QSpinBox[state="error"],
QDoubleSpinBox[state="error"], QDateEdit[state="error"], QDateTimeEdit[state="error"],
QTextEdit[state="error"], QPlainTextEdit[state="error"] {{
    border-color: {danger};
}}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QDateEdit:disabled, QDateTimeEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {background};
    color: {text_secondary};
    border-color: {border};
}}

QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text_primary};
    border: 1px solid {border};
    selection-background-color: {primary};
    selection-color: {on_primary};
    outline: none;
}}

QSlider::groove:horizontal {{
    background: {border};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {primary};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::sub-page:horizontal {{
    background: {primary};
    border-radius: 2px;
}}

QCalendarWidget QWidget {{
    background-color: {surface};
    color: {text_primary};
}}

QCalendarWidget QAbstractItemView:enabled {{
    background-color: {surface};
    color: {text_primary};
    selection-background-color: {primary};
    selection-color: {on_primary};
}}

QCalendarWidget QToolButton {{
    background-color: {surface};
    color: {text_primary};
}}

QCheckBox, QRadioButton {{
    background-color: transparent;
    color: {text_primary};
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    background-color: {surface};
    border: 2px solid {border};
    border-radius: {radius_sm_px}px;
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {text_secondary};
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {primary};
    border: 2px solid {primary};
}}

QCheckBox::indicator:checked:hover, QRadioButton::indicator:checked:hover {{
    background-color: {primary_hover};
    border-color: {primary_hover};
}}

QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background-color: {background};
    border-color: {border};
}}

QTabWidget::pane {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {radius_px}px;
}}

QTabBar::tab {{
    background-color: {background};
    color: {text_primary};
    border: 1px solid {border};
    border-bottom: none;
    padding: 10px 20px;
    font-size: {title_font_size_pt}pt;
    font-weight: bold;
}}

QTabBar::tab:selected {{
    background-color: {primary};
    color: {on_primary};
}}

QTabBar::tab:hover {{
    background-color: {hover_surface};
    color: {text_primary};
}}

QMenu {{
    background-color: {surface};
    color: {text_primary};
    border: 1px solid {border};
}}

QMenu::item {{
    background-color: {surface};
    color: {text_primary};
    padding: 4px 20px;
}}

QMenu::item:selected {{
    background-color: {primary};
    color: {on_primary};
}}

QToolTip {{
    background-color: {surface};
    color: {text_primary};
    border: 1px solid {border};
    padding: 4px;
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background-color: {background};
    border: none;
}}

QScrollBar:vertical {{
    width: 10px;
    margin: 0px;
}}

QScrollBar:horizontal {{
    height: 10px;
    margin: 0px;
}}

QScrollBar::handle {{
    background-color: {scrollbar_handle};
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    min-height: 24px;
}}

QScrollBar::handle:horizontal {{
    min-width: 24px;
}}

QScrollBar::handle:hover {{
    background-color: {primary};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
    border: none;
    background: none;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

QListWidget, QTableWidget, QTreeWidget {{
    background-color: {card_surface};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: {radius_px}px;
}}

QListWidget::item, QTableWidget::item, QTreeWidget::item {{
    background-color: {card_surface};
    color: {text_primary};
    padding: 4px;
}}

QListWidget::item:selected, QTableWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {primary};
    color: {on_primary};
}}

QListWidget::item:hover, QTableWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {hover_surface};
    color: {text_primary};
}}

QHeaderView::section {{
    background-color: {header_accent};
    color: {text_primary};
    border: 1px solid {border};
    padding: 10px 8px;
    font-weight: 700;
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

QLabel[role="warning"] {{
    color: {warning};
}}

QLabel[role="info"] {{
    color: {primary};
}}

QLabel[badge="true"] {{
    border-radius: {radius_sm_px}px;
    padding: 2px 10px;
    font-weight: 600;
}}

QLabel[badge="true"][role="success"] {{
    background-color: {success_tint};
    color: {success};
}}

QLabel[badge="true"][role="warning"] {{
    background-color: {warning_tint};
    color: {warning};
}}

QLabel[badge="true"][role="danger"] {{
    background-color: {danger_tint};
    color: {danger};
}}

QLabel[badge="true"][role="secondary"] {{
    background-color: {header_accent};
    color: {text_secondary};
}}

QLabel[role="title"] {{
    background-color: {primary};
    color: {on_primary};
    font-size: {title_font_size_pt}pt;
    font-weight: bold;
    border-radius: {radius_px}px;
    padding: 8px 14px;
}}

QLabel#dispatchBadge {{
    background-color: {danger};
    color: {on_primary};
    font-size: 14pt;
    font-weight: bold;
    border-radius: 15px;
    padding: 0 6px;
}}

QLabel[emphasis="true"] {{
    font-size: {title_font_size_pt}pt;
    font-weight: bold;
}}

QLabel[role="amount"] {{
    font-size: {amount_font_size_pt}pt;
    font-weight: bold;
}}

QLabel[role="hero"] {{
    font-size: {hero_font_size_pt}pt;
    font-weight: bold;
}}

QLabel[sizeVariant="status"] {{
    font-size: {status_font_size_pt}pt;
    font-weight: bold;
}}
"""


_HOVER_SHADE = -0.08
_PRESSED_SHADE = -0.16
_GRADIENT_SHADE = -0.06
"""Diferencia sutil entre el inicio y el final del degradado vertical de un
botón (§5, "gradiente muy suave") — más leve que el hover (`_HOVER_SHADE`),
para que el degradado se note como una superficie con volumen sin
confundirse con el estado de hover."""
_ACCENT_BORDER_ALPHA = 0.4
"""Fuerza del tinte del borde de acento de `KpiCard`/tarjeta de acceso
rápido (ver DESIGN_SYSTEM.md, sección "Tarjeta KPI con ícono y tendencia")
— sutil por diseño: comunica categoría sin competir con el color real de un
estado (éxito/alerta/error en `role=`)."""
_SCROLLBAR_HANDLE_ALPHA = 0.35
"""El handle de scroll se tiñe de `primary` sobre `background` en vez de
usar un gris neutro — mismo criterio "azul eléctrico sutil" que el borde de
las tarjetas."""


def generate_qss(tokens: ThemeTokens) -> str:
    """Genera el stylesheet Qt (QSS) correspondiente a un conjunto de
    tokens — incluye los tonos hover/pressed/degradado derivados de
    `primary`/`danger` (ver `_shade`), calculados acá y no guardados en
    `ThemeTokens` porque son puramente una necesidad de presentación."""
    values = dict(tokens.__dict__)
    values["primary_hover"] = _shade(tokens.primary, _HOVER_SHADE)
    values["primary_pressed"] = _shade(tokens.primary, _PRESSED_SHADE)
    values["primary_gradient_end"] = _shade(tokens.primary, _GRADIENT_SHADE)
    values["danger_hover"] = _shade(tokens.danger, _HOVER_SHADE)
    values["danger_pressed"] = _shade(tokens.danger, _PRESSED_SHADE)
    values["danger_gradient_end"] = _shade(tokens.danger, _GRADIENT_SHADE)
    values["accent_border_primary"] = _blend(
        tokens.primary, tokens.card_surface, _ACCENT_BORDER_ALPHA
    )
    values["accent_border_success"] = _blend(
        tokens.success, tokens.card_surface, _ACCENT_BORDER_ALPHA
    )
    values["accent_border_secondary"] = _blend(
        tokens.text_secondary, tokens.card_surface, _ACCENT_BORDER_ALPHA
    )
    values["scrollbar_handle"] = _blend(
        tokens.primary, tokens.background, _SCROLLBAR_HANDLE_ALPHA
    )
    return _QSS_TEMPLATE.format(**values)


_active_tokens: ThemeTokens = DARK_THEME
"""Copia del tema actualmente activo, accesible sin inyección de
dependencias — para código de presentación que solo necesita leer un
color (ej. `QAbstractTableModel.data()` con `BackgroundRole`/
`ForegroundRole`, donde exigir `ThemeManager` completo por DI sería
desproporcionado para un valor de solo lectura). `ThemeManager.apply()`
es la única función que la actualiza — ver DESIGN_SYSTEM.md §12."""


def get_active_tokens() -> ThemeTokens:
    """Tokens del tema actualmente activo. Reemplaza los colores
    hardcodeados que varios módulos definían por su cuenta (nunca
    reactivos a un cambio de tema) — ver DESIGN_SYSTEM.md §1.3/§12."""
    return _active_tokens


class ThemeManager:
    """Aplica un `ThemeTokens` a la `QApplication` activa."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._active: ThemeTokens = DARK_THEME

    @property
    def active(self) -> ThemeTokens:
        """Tokens del tema actualmente aplicado."""
        return self._active

    def apply(self, tokens: ThemeTokens) -> None:
        """Aplica el tema `tokens` a toda la aplicación."""
        global _active_tokens
        self._active = tokens
        _active_tokens = tokens
        self._app.setStyleSheet(generate_qss(tokens))

    def apply_dark(self) -> None:
        """Aplica el único tema oficial ("Cristal Oscuro")."""
        self.apply(DARK_THEME)
