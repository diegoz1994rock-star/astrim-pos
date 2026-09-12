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
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pos.modules.reports.application.dto import ChartPointDTO
from pos.modules.reports.domain.enums import ReportFormat
from pos.modules.reports.presentation.reports_view_model import ReportKind, ReportsViewModel
from pos.shared_ui.theme.spacing import SPACING_SM, SPACING_XS
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.simple_bar_chart import ChartSeriesPoint, SimpleBarChart
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_CHART_PERIODS = ["Diario (últimos 30 días)", "Mensual (últimos 12 meses)"]
_LEGEND_SWATCH_PX = 12


def _legend_item(color_hex: str, text: str, parent: QWidget) -> QWidget:
    """Par de swatch de color + texto para la leyenda del gráfico — antes
    era un emoji de cuadrado de color (🟦/🟩), que no obedece al tema ni a
    la familia de íconos del resto de la app (ver DESIGN_SYSTEM.md §10)."""
    item = QWidget(parent)
    layout = QHBoxLayout(item)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SPACING_XS)
    swatch = QFrame(item)
    swatch.setFixedSize(_LEGEND_SWATCH_PX, _LEGEND_SWATCH_PX)
    swatch.setStyleSheet(f"background-color: {color_hex}; border-radius: 2px;")
    layout.addWidget(swatch)
    layout.addWidget(QLabel(text, item))
    return item


class ReportsView(QWidget):
    def __init__(self, view_model: ReportsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._build_ui()
        self._connect_signals()
        self._on_chart_refresh_clicked()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(make_section_title("Reportes"))

        tabs = QTabWidget(self)
        tabs.addTab(self._build_tables_tab(), "Tablas")
        tabs.addTab(self._build_charts_tab(), "Gráficas")
        outer_layout.addWidget(tabs)

    def _build_tables_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(page)
        outer.addWidget(scroll_area)

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
        return page

    def _build_charts_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(page)
        outer.addWidget(scroll_area)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Período:"))
        self._chart_period_combo = QComboBox(self)
        self._chart_period_combo.addItems(_CHART_PERIODS)
        controls.addWidget(self._chart_period_combo)
        self._chart_refresh_button = QPushButton("Actualizar")
        controls.addWidget(self._chart_refresh_button)
        controls.addStretch()
        layout.addLayout(controls)

        legend = QHBoxLayout()
        legend.setSpacing(SPACING_SM)
        tokens = get_active_tokens()
        legend.addWidget(_legend_item(tokens.primary, "Ventas", page))
        legend.addWidget(_legend_item(tokens.success, "Ganancias", page))
        legend.addStretch(1)
        layout.addLayout(legend)

        self._chart = SimpleBarChart(self)
        self._chart.setMinimumHeight(360)
        layout.addWidget(self._chart)
        return page

    def _connect_signals(self) -> None:
        self._generate_button.clicked.connect(self._on_generate_clicked)
        self._export_pdf_button.clicked.connect(lambda: self._on_export_clicked(ReportFormat.PDF))
        self._export_excel_button.clicked.connect(
            lambda: self._on_export_clicked(ReportFormat.EXCEL)
        )
        self._chart_refresh_button.clicked.connect(self._on_chart_refresh_clicked)
        self._chart_period_combo.currentIndexChanged.connect(self._on_chart_refresh_clicked)
        self._view_model.report_ready.connect(self._on_report_ready)
        self._view_model.chart_ready.connect(self._on_chart_ready)
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
        fit_table_to_contents(self._table)

    def _on_chart_refresh_clicked(self) -> None:
        monthly = self._chart_period_combo.currentIndex() == 1
        today = date.today()
        if monthly:
            """"Últimos 12 meses" son 12 baldes de mes, el actual incluido —
            `date(today.year - 1, today.month, 1)` daba 13 (el mismo mes
            hace un año Y el mes actual). Resta 11 meses al primer día del
            mes actual en vez de 12."""
            month_index = today.month - 1 - 11
            date_from = date(today.year + month_index // 12, month_index % 12 + 1, 1)
        else:
            # "Últimos 30 días" son 30 días incluyendo hoy, no 31.
            date_from = today - timedelta(days=29)
        self._view_model.generate_chart(monthly, date_from, today)

    def _on_chart_ready(self, points: list[ChartPointDTO]) -> None:
        self._chart.set_data(
            [
                ChartSeriesPoint(
                    label=point.label, sales_total=point.sales_total, profit_total=point.profit_total
                )
                for point in points
            ]
        )

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
        show_toast(self, message)
