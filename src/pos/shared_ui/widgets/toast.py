"""Notificación no bloqueante ("toast") para confirmaciones de guardado
exitoso — ver DESIGN_SYSTEM.md §11.

Reemplaza `QMessageBox.information()` para el caso específico de "la
operación ya se completó con éxito, esto es solo una confirmación" — un
`QMessageBox` modal exige un clic extra para cerrarlo, en la acción más
frecuente de toda la app (guardar). Nunca reemplaza `QMessageBox.warning`:
un error sí debe detener al usuario hasta que lo lea, eso no cambia."""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from pos.shared_ui.theme.elevation import apply_shadow
from pos.shared_ui.theme.spacing import SPACING_MD
from pos.shared_ui.theme.theme_manager import get_active_tokens

_DISPLAY_MS = 2500
_FADE_MS = 150
_MARGIN_PX = 24
_MAX_WIDTH_PX = 360

_active_toasts: set[_Toast] = set()
"""Referencia fuerte a cada toast en pantalla. Es una ventana propia sin
padre Qt (`parent=None` en `super().__init__`, ver docstring de `_Toast`)
— sin esto, nada evita que el recolector de basura de Python libere el
objeto apenas `show_toast()` retorna, aunque la ventana siga visible en
pantalla (síntoma real encontrado durante la verificación de esta fase:
el toast desaparecía de inmediato, antes de que corriera la animación)."""


class _Toast(QLabel):
    """Ventana propia (no un hijo dentro del layout de `parent`) para
    poder animar `windowOpacity` — una animación de opacidad por
    `QGraphicsEffect` no puede convivir con la sombra de elevación
    (`apply_shadow`, ver su docstring: un widget solo admite un efecto
    gráfico a la vez), mientras que `windowOpacity` es una propiedad de
    composición nativa de la ventana, independiente del efecto gráfico."""

    def __init__(self, message: str, parent: QWidget) -> None:
        super().__init__(message, None)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWordWrap(True)
        self.setMaximumWidth(_MAX_WIDTH_PX)
        self.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)

        tokens = get_active_tokens()
        self.setStyleSheet(
            f"background-color: {tokens.card_surface}; color: {tokens.text_primary}; "
            f"border: 1px solid {tokens.border}; border-radius: {tokens.radius_px}px; "
            f"font-size: {tokens.font_size_pt}pt;"
        )
        apply_shadow(self, "lg", glow_color=tokens.primary)

        self.adjustSize()
        self._position(parent)

        self.setWindowOpacity(0.0)
        self.show()

        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(_FADE_MS)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.start()

        self._fade_out: QPropertyAnimation | None = None
        _active_toasts.add(self)
        QTimer.singleShot(_DISPLAY_MS, self._start_fade_out)

    def _position(self, parent: QWidget) -> None:
        anchor = parent.mapToGlobal(parent.rect().bottomRight())
        self.move(anchor.x() - self.width() - _MARGIN_PX, anchor.y() - self.height() - _MARGIN_PX)

    def _start_fade_out(self) -> None:
        self._fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out.setDuration(_FADE_MS)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self._close)
        self._fade_out.start()

    def _close(self) -> None:
        _active_toasts.discard(self)
        self.deleteLater()


def show_toast(parent: QWidget, message: str) -> None:
    """Muestra una confirmación breve y no bloqueante anclada
    abajo-a-la-derecha de `parent`, con una entrada suave (`_FADE_MS`) y
    salida automática a los `_DISPLAY_MS`. No hace falta guardar la
    referencia devuelta — no devuelve nada — el widget se autodestruye
    (`deleteLater`) al terminar de desvanecerse."""
    _Toast(message, parent)
