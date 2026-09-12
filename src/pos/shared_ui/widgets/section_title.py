"""Título de sección/pantalla, destacado visualmente (ver
`QLabel[role="title"]` en `shared_ui/theme/theme_manager.py`).

No usa `QLabel.setFont(...)` con una fuente capturada a mano: si se llama
antes de que el widget se muestre por primera vez, `.font()` devuelve la
fuente por defecto de Qt en vez de la del stylesheet de la app (la familia
elegida — ver `tokens.py` — todavía no se resolvió), y esa fuente
incorrecta queda fija incluso después de mostrarse. Usar la propiedad
`role="title"` deja que el stylesheet resuelva tipografía y color siempre
correctamente, sin importar el orden de construcción."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget


def make_section_title(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("role", "title")
    return label
