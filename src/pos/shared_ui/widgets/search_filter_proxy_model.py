"""Filtro de tabla en vivo compartido — el proxy no conoce nada de
Producto/Inventario: cada modelo de origen expone, en `SEARCH_ROLE` sobre
la columna 0, el texto combinado de sus propios campos buscables (SKU +
códigos de barras + nombre + categoría, u otra combinación); este proxy
solo decide si ese texto contiene la búsqueda actual."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QObject, QSortFilterProxyModel, Qt

SEARCH_ROLE = Qt.ItemDataRole.UserRole + 1


class SearchFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._query = ""

    def set_search_text(self, text: str) -> None:
        self._query = text.strip().lower()
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._query:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        index = model.index(source_row, 0, source_parent)
        haystack = model.data(index, SEARCH_ROLE)
        return bool(haystack) and self._query in str(haystack).lower()
