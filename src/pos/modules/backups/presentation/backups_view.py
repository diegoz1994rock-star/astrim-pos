"""Pantalla de backups: copias manuales, trabajos programados, historial
profesional (scroll real, columnas ajustables, orden y detalle) y
restauración verificada."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.backups.application.dto import BackupHistoryDTO
from pos.modules.backups.domain.enums import BackupOrigin, BackupStatus
from pos.modules.backups.presentation.backup_detail_dialog import BackupDetailDialog
from pos.modules.backups.presentation.backups_view_model import (
    BackupsSummaryDisplay,
    BackupsViewModel,
)
from pos.modules.backups.presentation.schedule_backup_dialog import ScheduleBackupDialog
from pos.shared_ui.formatting import format_file_size
from pos.shared_ui.widgets.kpi_card import KpiCard
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.toast import show_toast

_HISTORY_COLUMNS = [
    "Fecha",
    "Hora",
    "Estado",
    "Nombre del archivo",
    "Ruta",
    "Tamaño",
    "Tipo",
    "Versión del sistema",
    "Usuario",
]
_ROW_HEIGHT = 40
_MIN_COLUMN_WIDTH = 110
_TABLE_HEIGHT = 480

_DB_FILTER = "Bases de datos (*.db)"

_ORIGIN_LABELS = {
    BackupOrigin.MANUAL: "Manual",
    BackupOrigin.SCHEDULED: "Automático",
    BackupOrigin.IMPORTED: "Importado",
}

_STATUS_ROLES = {
    BackupStatus.SUCCESS: "success",
    BackupStatus.FAILED: "danger",
    BackupStatus.IN_PROGRESS: "warning",
}


class _SortableItem(QTableWidgetItem):
    """`QTableWidgetItem` que ordena por una clave real (`sort_key`, ej. un
    timestamp o el tamaño en bytes) en vez de comparar el texto ya
    formateado que se muestra en la celda."""

    def __init__(self, text: str, sort_key: Any) -> None:
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other: object) -> bool:
        if isinstance(other, _SortableItem):
            return bool(self._sort_key < other._sort_key)
        if isinstance(other, QTableWidgetItem):
            return bool(super().__lt__(other))
        return NotImplemented


def _configure_wide_table(table: QTableWidget) -> None:
    """Tabla de historial con scroll horizontal y vertical real, de tamaño
    fijo — no crece con la cantidad de backups (punto 3 del pedido: "debe
    mantenerse siempre del mismo tamaño")."""
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setMinimumSectionSize(_MIN_COLUMN_WIDTH)
    table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSortingEnabled(True)
    table.setFixedHeight(_TABLE_HEIGHT)


class BackupsView(QWidget):
    def __init__(self, view_model: BackupsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._history: list[BackupHistoryDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        title = make_section_title("Backups")
        layout.addWidget(title)

        actions = QHBoxLayout()
        self._manual_backup_button = QPushButton("Crear backup ahora")
        self._new_job_button = QPushButton("Programar backup automático")
        self._search_button = QPushButton("Buscar backups")
        self._restore_button = QPushButton("Restaurar seleccionado")
        self._restore_button.setEnabled(False)
        actions.addWidget(self._manual_backup_button)
        actions.addWidget(self._new_job_button)
        actions.addWidget(self._search_button)
        actions.addWidget(self._restore_button)
        layout.addLayout(actions)

        layout.addWidget(QLabel("Programación actual"))
        self._schedule_description_label = QLabel("")
        self._schedule_description_label.setWordWrap(True)
        layout.addWidget(self._schedule_description_label)

        summary_row = QHBoxLayout()
        self._manual_count_card = KpiCard("Backups manuales", "0")
        self._automatic_count_card = KpiCard("Backups automáticos", "0")
        self._space_used_card = KpiCard("Espacio utilizado", "0 B")
        self._last_backup_card = KpiCard("Último backup realizado", "N/D")
        self._next_backup_card = KpiCard("Próximo backup automático", "Sin programación")
        for card in (
            self._manual_count_card,
            self._automatic_count_card,
            self._space_used_card,
            self._last_backup_card,
            self._next_backup_card,
        ):
            summary_row.addWidget(card)
        layout.addLayout(summary_row)

        layout.addWidget(make_section_title("Historial"))
        self._history_table = QTableWidget(0, len(_HISTORY_COLUMNS), self)
        self._history_table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        _configure_wide_table(self._history_table)
        layout.addWidget(self._history_table)

    def _connect_signals(self) -> None:
        self._manual_backup_button.clicked.connect(self._on_manual_backup_clicked)
        self._new_job_button.clicked.connect(self._on_schedule_clicked)
        self._search_button.clicked.connect(self._on_search_clicked)
        self._restore_button.clicked.connect(self._on_restore_clicked)
        self._history_table.itemSelectionChanged.connect(self._on_selection_changed)
        self._history_table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._view_model.schedule_loaded.connect(self._on_schedule_loaded)
        self._view_model.history_loaded.connect(self._on_history_loaded)
        self._view_model.summary_loaded.connect(self._on_summary_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_schedule_loaded(self, description: str) -> None:
        self._schedule_description_label.setText(description)

    def _on_summary_loaded(self, summary: BackupsSummaryDisplay) -> None:
        self._manual_count_card.set_value(str(summary.manual_count))
        self._automatic_count_card.set_value(str(summary.automatic_count))
        self._space_used_card.set_value(format_file_size(summary.total_size_bytes))
        self._last_backup_card.set_value(
            summary.last_backup_at.astimezone().strftime("%Y-%m-%d %H:%M")
            if summary.last_backup_at
            else "N/D"
        )
        self._next_backup_card.set_value(
            summary.next_scheduled_at.astimezone().strftime("%Y-%m-%d %H:%M")
            if summary.next_scheduled_at
            else "Sin programación"
        )

    def _on_history_loaded(self, history: list[BackupHistoryDTO]) -> None:
        self._history = history
        self._history_table.setSortingEnabled(False)
        self._history_table.setRowCount(len(history))
        for row, entry in enumerate(history):
            self._fill_row(row, entry)
        self._history_table.setSortingEnabled(True)
        self._on_selection_changed()

    def _fill_row(self, row: int, entry: BackupHistoryDTO) -> None:
        local_started = entry.started_at.astimezone()
        file_name = Path(entry.file_path).name if entry.file_path else "N/D"
        size_text = format_file_size(entry.size_bytes) if entry.size_bytes is not None else "N/D"
        status_column = 2
        cells = [
            _SortableItem(local_started.strftime("%Y-%m-%d"), local_started),
            _SortableItem(local_started.strftime("%H:%M:%S"), local_started),
            QTableWidgetItem(entry.status.value),
            QTableWidgetItem(file_name),
            QTableWidgetItem(entry.file_path or "N/D"),
            _SortableItem(size_text, entry.size_bytes or 0),
            QTableWidgetItem(_ORIGIN_LABELS[entry.origin]),
            QTableWidgetItem(entry.app_version or "Desconocida"),
            QTableWidgetItem(entry.created_by_username or _ORIGIN_LABELS[entry.origin]),
        ]
        for column, item in enumerate(cells):
            item.setToolTip(item.text())
            self._history_table.setItem(row, column, item)
        cells[0].setData(Qt.ItemDataRole.UserRole, entry.id)
        # `setItem` arriba deja la celda ordenable por texto; el chip se
        # superpone visualmente encima sin perder esa capacidad de orden.
        self._history_table.setCellWidget(
            row, status_column, StatusBadge(entry.status.value, _STATUS_ROLES[entry.status])
        )

    def _selected_entry(self) -> BackupHistoryDTO | None:
        selected_rows = self._history_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row_item = self._history_table.item(selected_rows[0].row(), 0)
        if row_item is None:
            return None
        entry_id = row_item.data(Qt.ItemDataRole.UserRole)
        return next((entry for entry in self._history if entry.id == entry_id), None)

    def _on_selection_changed(self) -> None:
        self._restore_button.setEnabled(self._selected_entry() is not None)

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        row_item = self._history_table.item(row, 0)
        if row_item is None:
            return
        entry_id = row_item.data(Qt.ItemDataRole.UserRole)
        entry = next((e for e in self._history if e.id == entry_id), None)
        if entry is not None:
            BackupDetailDialog(entry, parent=self).exec()

    def _on_manual_backup_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Carpeta destino del backup")
        destination_dir = Path(directory) if directory else None
        self._view_model.run_manual_backup(destination_dir)

    def _on_search_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Buscar backups", "", _DB_FILTER)
        if not path:
            return
        self._view_model.import_backup_file(Path(path))

    def _on_schedule_clicked(self) -> None:
        frequency, hour, minute, backup_on_close = self._view_model.current_schedule_state()
        dialog = ScheduleBackupDialog(
            initial_frequency=frequency,
            initial_hour=hour,
            initial_minute=minute,
            initial_backup_on_close=backup_on_close,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dialog_hour, dialog_minute = dialog.selected_time()
        self._view_model.save_schedule(
            dialog.selected_frequency(),
            dialog_hour,
            dialog_minute,
            dialog.backup_on_close_enabled(),
        )

    def _on_restore_clicked(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self._show_error("Selecciona un backup del historial.")
            return

        verification = self._view_model.verify_backup(entry.id)
        if verification is None:
            return
        if not verification.ok:
            self._show_error(verification.reason or "El backup no es válido.")
            return

        confirmation = QMessageBox.question(
            self,
            "Confirmar restauración",
            "Se restaurará el sistema utilizando el backup seleccionado. "
            "Esta acción reemplazará la información actual. ¿Desea continuar?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self._view_model.restore(entry.id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
