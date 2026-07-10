"""Pantalla de backups: copias manuales, trabajos programados, historial y restauración."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
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

from pos.modules.backups.application.dto import BackupHistoryDTO, BackupJobDTO
from pos.modules.backups.presentation.backups_view_model import BackupsViewModel

_HISTORY_COLUMNS = ["Inicio", "Estado", "Archivo", "Tamaño (bytes)"]


class BackupsView(QWidget):
    def __init__(self, view_model: BackupsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._history: list[BackupHistoryDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Backups")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)

        actions = QHBoxLayout()
        self._manual_backup_button = QPushButton("Crear backup ahora")
        self._new_job_button = QPushButton("Programar backup automático")
        self._restore_button = QPushButton("Restaurar seleccionado")
        actions.addWidget(self._manual_backup_button)
        actions.addWidget(self._new_job_button)
        actions.addWidget(self._restore_button)
        layout.addLayout(actions)

        layout.addWidget(QLabel("Trabajos programados:"))
        self._jobs_label = QLabel("(ninguno)")
        self._jobs_label.setWordWrap(True)
        layout.addWidget(self._jobs_label)

        layout.addWidget(QLabel("Historial:"))
        self._history_table = QTableWidget(0, len(_HISTORY_COLUMNS), self)
        self._history_table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        self._history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._history_table)

    def _connect_signals(self) -> None:
        self._manual_backup_button.clicked.connect(self._on_manual_backup_clicked)
        self._new_job_button.clicked.connect(self._on_new_job_clicked)
        self._restore_button.clicked.connect(self._on_restore_clicked)
        self._view_model.jobs_loaded.connect(self._on_jobs_loaded)
        self._view_model.history_loaded.connect(self._on_history_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_jobs_loaded(self, jobs: list[BackupJobDTO]) -> None:
        if not jobs:
            self._jobs_label.setText("(ninguno)")
            return
        self._jobs_label.setText(
            "\n".join(
                f"{job.name} — {job.schedule_cron or 'manual'} — "
                f"{'activo' if job.is_active else 'inactivo'}"
                for job in jobs
            )
        )

    def _on_history_loaded(self, history: list[BackupHistoryDTO]) -> None:
        self._history = history
        self._history_table.setRowCount(len(history))
        for row, entry in enumerate(history):
            self._history_table.setItem(
                row, 0, QTableWidgetItem(f"{entry.started_at:%Y-%m-%d %H:%M}")
            )
            self._history_table.setItem(row, 1, QTableWidgetItem(entry.status.value))
            self._history_table.setItem(row, 2, QTableWidgetItem(entry.file_path or ""))
            self._history_table.setItem(
                row, 3, QTableWidgetItem(str(entry.size_bytes) if entry.size_bytes else "")
            )

    def _on_manual_backup_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Carpeta destino del backup")
        destination_dir = Path(directory) if directory else None
        self._view_model.run_manual_backup(destination_dir)

    def _on_new_job_clicked(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nuevo trabajo", "Nombre:")
        if not accepted or not name.strip():
            return
        cron_expression, accepted = QInputDialog.getText(
            self, "Programación", "Expresión cron (ej. '0 2 * * *' = 2am diario):"
        )
        if not accepted:
            return
        self._view_model.create_job(name, cron_expression, "")

    def _on_restore_clicked(self) -> None:
        selected_rows = self._history_table.selectionModel().selectedRows()
        if not selected_rows:
            self._show_error("Selecciona un backup del historial.")
            return
        entry = self._history[selected_rows[0].row()]
        if entry.file_path is None:
            self._show_error("Este registro de historial no tiene un archivo asociado.")
            return
        confirmation = QMessageBox.question(
            self,
            "Confirmar restauración",
            "Esto reemplazará todos los datos actuales por los del backup seleccionado. "
            "¿Continuar?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self._view_model.restore(Path(entry.file_path))

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
