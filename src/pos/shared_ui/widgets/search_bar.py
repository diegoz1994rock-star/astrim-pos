"""Buscador en vivo reutilizable — Catálogo → Productos e Inventario →
Existencias comparten esta misma pieza en vez de cada uno reimplementar su
propio campo de búsqueda."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget


class SearchBar(QWidget):
    text_changed = Signal(str)

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(f"🔍 {placeholder}")
        self._edit.setClearButtonEnabled(True)
        self._edit.textChanged.connect(self.text_changed)
        layout.addWidget(self._edit)

    def focus(self) -> None:
        """Usado por el atajo Ctrl+F de cada pantalla."""
        self._edit.setFocus()
        self._edit.selectAll()

    def text(self) -> str:
        return self._edit.text()
