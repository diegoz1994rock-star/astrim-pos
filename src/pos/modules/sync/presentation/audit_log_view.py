"""Pantalla de Auditoría: bitácora legible de acciones del sistema (ventas,
anulaciones, cambios de stock, etc.), reutilizando el outbox de
Sincronización (`sync_log`) que ya captura todo evento de dominio."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.sync.application.dto import SyncLogEntryDTO
from pos.modules.sync.presentation.audit_log_view_model import AuditLogViewModel
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Hora", "Descripción", "Tipo de evento", "Origen"]


class AuditLogView(QWidget):
    def __init__(self, view_model: AuditLogViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        toolbar = QHBoxLayout()
        title = make_section_title("Auditoría")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._refresh_button = QPushButton("Actualizar")
        toolbar.addWidget(self._refresh_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._refresh_button.clicked.connect(self._on_refresh_clicked)
        self._view_model.entries_loaded.connect(self._on_entries_loaded)

    def _on_refresh_clicked(self) -> None:
        self._view_model.load()

    def _on_entries_loaded(self, entries: list[tuple[SyncLogEntryDTO, str]]) -> None:
        self._table.setRowCount(len(entries))
        for row, (entry, description) in enumerate(entries):
            values = [
                entry.created_at.strftime("%d/%m/%Y %H:%M"),
                description,
                entry.event_type,
                entry.origin_station_name,
            ]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))
        fit_table_to_contents(self._table)
