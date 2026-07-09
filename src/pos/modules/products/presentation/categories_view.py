"""Pantalla de administración de categorías."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.products.application.dto import CategoryDTO
from pos.modules.products.presentation.categories_view_model import CategoriesViewModel

_COLUMNS = ["Nombre", "Categoría padre", "Estado"]


class CategoriesView(QWidget):
    def __init__(self, view_model: CategoriesViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._categories: list[CategoryDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Categorías")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nueva categoría")
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        self._toggle_button = QPushButton("Activar/Desactivar seleccionada")
        layout.addWidget(self._toggle_button)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._view_model.categories_loaded.connect(self._on_categories_loaded)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_categories_loaded(self, categories: list[CategoryDTO]) -> None:
        self._categories = categories
        self._table.setRowCount(len(categories))
        for row, category in enumerate(categories):
            self._table.setItem(row, 0, QTableWidgetItem(category.name))
            self._table.setItem(row, 1, QTableWidgetItem(category.parent_name or ""))
            self._table.setItem(
                row, 2, QTableWidgetItem("Activa" if category.is_active else "Inactiva")
            )

    def _on_new_clicked(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nueva categoría", "Nombre:")
        if not accepted or not name.strip():
            return

        parent_names = ["(ninguna)"] + [c.name for c in self._categories]
        parent_name, accepted = QInputDialog.getItem(
            self, "Categoría padre", "Categoría padre (opcional):", parent_names, editable=False
        )
        parent_id = None
        if accepted and parent_name != "(ninguna)":
            parent_id = next(c.id for c in self._categories if c.name == parent_name)

        self._view_model.create_category(name.strip(), parent_id)

    def _on_toggle_clicked(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            self._show_error("Selecciona una categoría de la tabla.")
            return
        category = self._categories[selected_rows[0].row()]
        self._view_model.set_active(category.id, not category.is_active)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
