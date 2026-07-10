"""Pantalla de reportes: selección de tipo/rango, tabla de resultados y
exportación a PDF/Excel."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
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

from pos.modules.reports.domain.enums import ReportFormat
from pos.modules.reports.presentation.reports_view_model import ReportKind, ReportsViewModel


class ReportsView(QWidget):
    def __init__(self, view_model: ReportsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Reportes")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)

        controls = QHBoxLayout()
        self._kind_combo = QComboBox(self)
        for kind in ReportKind:
            self._kind_combo.addItem(kind.value, userData=kind)
        controls.addWidget(self._kind_combo)

        thirty_days_ago = date.today() - timedelta(days=30)
        self._date_from_edit = QDateEdit(self)
        self._date_from_edit.setCalendarPopup(True)
        self._date_from_edit.setDate(
            QDate(thirty_days_ago.year, thirty_days_ago.month, thirty_days_ago.day)
        )
        today = date.today()
        self._date_to_edit = QDateEdit(self)
        self._date_to_edit.setCalendarPopup(True)
        self._date_to_edit.setDate(QDate(today.year, today.month, today.day))
        controls.addWidget(QLabel("Desde"))
        controls.addWidget(self._date_from_edit)
        controls.addWidget(QLabel("Hasta"))
        controls.addWidget(self._date_to_edit)

        self._generate_button = QPushButton("Generar")
        controls.addWidget(self._generate_button)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 0, self)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        export_row = QHBoxLayout()
        self._export_pdf_button = QPushButton("Exportar a PDF")
        self._export_excel_button = QPushButton("Exportar a Excel")
        export_row.addWidget(self._export_pdf_button)
        export_row.addWidget(self._export_excel_button)
        layout.addLayout(export_row)

    def _connect_signals(self) -> None:
        self._generate_button.clicked.connect(self._on_generate_clicked)
        self._export_pdf_button.clicked.connect(lambda: self._on_export_clicked(ReportFormat.PDF))
        self._export_excel_button.clicked.connect(
            lambda: self._on_export_clicked(ReportFormat.EXCEL)
        )
        self._view_model.report_ready.connect(self._on_report_ready)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_generate_clicked(self) -> None:
        kind = self._kind_combo.currentData()
        date_from = self._date_from_edit.date()
        date_to = self._date_to_edit.date()
        self._view_model.generate(
            kind,
            date(date_from.year(), date_from.month(), date_from.day()),
            date(date_to.year(), date_to.month(), date_to.day()),
        )

    def _on_report_ready(self, headers: list[str], rows: list[list[str]]) -> None:
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                self._table.setItem(row_index, col_index, QTableWidgetItem(value))

    def _on_export_clicked(self, report_format: ReportFormat) -> None:
        extension = "pdf" if report_format is ReportFormat.PDF else "xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar reporte", f"reporte.{extension}", f"*.{extension}"
        )
        if not file_path:
            return
        self._view_model.export(report_format, Path(file_path))

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
