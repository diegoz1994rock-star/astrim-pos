"""Selector de color para el editor visual de plantillas de factura:
una paleta curada de ~20 colores (claros y oscuros) más un botón que abre
`QColorDialog` para cualquier color personalizado. Primer color-picker
del repositorio — los colores de la paleta son deliberadamente literales
(son las opciones en sí, no cromado de la app), no deben tomarse de
`ThemeTokens`."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QGridLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pos.shared_ui.theme.theme_manager import get_active_tokens

PALETTE: list[tuple[str, str]] = [
    ("Negro", "#000000"),
    ("Blanco", "#FFFFFF"),
    ("Gris oscuro", "#4D4D4D"),
    ("Gris claro", "#CCCCCC"),
    ("Azul marino", "#1B2A4A"),
    ("Azul rey", "#2547D6"),
    ("Azul cielo", "#87CEFA"),
    ("Celeste", "#A9E1F5"),
    ("Turquesa", "#40E0D0"),
    ("Verde oscuro", "#1B5E20"),
    ("Verde esmeralda", "#50C878"),
    ("Verde oliva", "#808000"),
    ("Rojo intenso", "#E10600"),
    ("Rojo vino", "#722F37"),
    ("Naranja", "#FF8C00"),
    ("Amarillo dorado", "#FFC107"),
    ("Morado", "#6A0DAD"),
    ("Lila", "#C8A2C8"),
    ("Rosado", "#FF69B4"),
    ("Café", "#6F4E37"),
]

_SWATCH_SIZE = 22
_COLUMNS = 5


class ColorPickerWidget(QWidget):
    """Emite `color_changed(hex)` cuando el usuario elige un swatch de la
    paleta o confirma un color personalizado."""

    color_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_hex = PALETTE[0][1]
        self._swatches: dict[str, QToolButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        grid.setSpacing(4)
        for index, (name, hex_value) in enumerate(PALETTE):
            button = QToolButton(self)
            button.setCheckable(True)
            button.setFixedSize(_SWATCH_SIZE, _SWATCH_SIZE)
            button.setToolTip(name)
            button.setStyleSheet(
                f"QToolButton {{ background-color: {hex_value}; border: 1px solid #888888; }}"
                f"QToolButton:checked {{ border: 2px solid {get_active_tokens().primary}; }}"
            )
            button.clicked.connect(lambda _checked, h=hex_value: self._select(h))
            grid.addWidget(button, index // _COLUMNS, index % _COLUMNS)
            self._swatches[hex_value.upper()] = button
        layout.addLayout(grid)

        self._custom_button = QPushButton("Personalizado…", self)
        self._custom_button.clicked.connect(self._open_custom_dialog)
        layout.addWidget(self._custom_button)

        self._select(self._current_hex, emit=False)

    def current_color(self) -> str:
        return self._current_hex

    def set_color(self, hex_value: str) -> None:
        self._select(hex_value, emit=False)

    def _select(self, hex_value: str, *, emit: bool = True) -> None:
        self._current_hex = hex_value.upper()
        for value, button in self._swatches.items():
            button.setChecked(value == self._current_hex)
        if emit:
            self.color_changed.emit(self._current_hex)

    def _open_custom_dialog(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._current_hex), self, "Elegir color")
        if chosen.isValid():
            self._select(chosen.name().upper())
