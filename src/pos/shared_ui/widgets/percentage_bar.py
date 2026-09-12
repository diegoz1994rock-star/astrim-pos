"""Barra de progreso horizontal (ej. "porcentaje del período de licencia
consumido") — no existe `QProgressBar` en ningún otro lugar de la app ni
una regla QSS para él; en vez de introducir un widget nativo sin estilo
propio, esto reutiliza el mismo patrón visual del resto de la app (2
`QFrame` anidados: pista + relleno), coloreado con los tokens del tema
activo, nunca colores hardcodeados (ver DESIGN_SYSTEM.md §1.3)."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QWidget

from pos.shared_ui.theme.theme_manager import get_active_tokens

_BAR_HEIGHT_PX = 8

_ROLE_COLOR_FIELDS = {
    "primary": "primary",
    "success": "success",
    "warning": "warning",
    "danger": "danger",
}


class PercentageBar(QWidget):
    """`set_percentage(value, role)` — `value` se recorta a [0, 100];
    `role` elige el color del relleno (mismo vocabulario semántico que
    `QLabel[role=...]`: `"primary"|"success"|"warning"|"danger"`)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_BAR_HEIGHT_PX)
        tokens = get_active_tokens()

        self._track = QFrame(self)
        self._track.setStyleSheet(
            f"background-color: {tokens.border}; border-radius: {_BAR_HEIGHT_PX // 2}px;"
        )

        self._fill = QFrame(self._track)
        self._fill.setStyleSheet(
            f"background-color: {tokens.primary}; border-radius: {_BAR_HEIGHT_PX // 2}px;"
        )

        self._percentage = 0.0

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._apply_geometry()

    def set_percentage(self, value: float, role: str = "primary") -> None:
        self._percentage = max(0.0, min(100.0, value))
        color_field = _ROLE_COLOR_FIELDS.get(role, "primary")
        color_hex = getattr(get_active_tokens(), color_field)
        self._fill.setStyleSheet(
            f"background-color: {color_hex}; border-radius: {_BAR_HEIGHT_PX // 2}px;"
        )
        self._apply_geometry()

    def percentage(self) -> float:
        return self._percentage

    def _apply_geometry(self) -> None:
        """Recalcula la pista y el relleno a partir del ancho real del
        widget (`self.width()`) en vez de depender de que `_track` ya
        tenga su geometría aplicada — evita que un `set_percentage()`
        llamado antes de que Qt procese un `resizeEvent()` pendiente use
        un ancho de pista todavía desactualizado."""
        width, height = self.width(), self.height()
        self._track.setGeometry(0, 0, width, height)
        fill_width = int(width * (self._percentage / 100.0))
        self._fill.setGeometry(0, 0, fill_width, height)
