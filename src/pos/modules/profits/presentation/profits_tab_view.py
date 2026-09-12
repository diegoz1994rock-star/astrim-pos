"""Contenido compartido por las 6 pestañas de Ganancias — filtros, tarjetas
resumen, tabla (con agrupación por categoría), Top 10, gráficos y botones
de exportación. Una sola clase, instanciada una vez por pestaña (ver
`profits_view.py`) — "no repetir código", tal como pide el pedido."""

from __future__ import annotations

import tempfile
from datetime import date as date_
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QDate, QModelIndex, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from pos.core.security.session import SessionManager
from pos.modules.cash_register.application.dto import CashRegisterDTO
from pos.modules.customers.application.dto import CustomerDTO
from pos.modules.inventory.application.dto import WarehouseDTO
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.products.application.dto import CategoryDTO
from pos.modules.profits.application.dto import (
    ChartSeriesDTO,
    ProductProfitRowDTO,
    ProfitSummaryDTO,
    TopListsDTO,
)
from pos.modules.profits.application.export_formatting import format_quantity
from pos.modules.profits.domain.enums import DateRangePreset, ProfitSortOption
from pos.modules.profits.domain.filters import ProfitFilters
from pos.modules.profits.presentation.product_sale_history_dialog import (
    ProductSaleHistoryDialog,
)
from pos.modules.profits.presentation.profits_table_model import (
    CategoryProfitTableModel,
    ProfitProductTableModel,
)
from pos.modules.profits.presentation.profits_view_model import ProfitsViewModel
from pos.modules.suppliers.application.dto import SupplierDTO
from pos.modules.users.application.dto import UserDTO
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.widgets.kpi_card import KpiCard
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.search_bar import SearchBar
from pos.shared_ui.widgets.search_filter_proxy_model import SearchFilterProxyModel
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.simple_area_chart import AreaChartPoint, SimpleAreaChart
from pos.shared_ui.widgets.simple_bar_chart import ChartSeriesPoint, SimpleBarChart
from pos.shared_ui.widgets.simple_line_chart import LineChartPoint, SimpleLineChart
from pos.shared_ui.widgets.simple_pie_chart import PieChartSlice, SimplePieChart
from pos.shared_ui.widgets.toast import show_toast

_PRESET_LABELS = {
    DateRangePreset.DAILY: "Diario",
    DateRangePreset.WEEKLY: "Semanal",
    DateRangePreset.MONTHLY: "Mensual",
    DateRangePreset.QUARTERLY: "Trimestral",
    DateRangePreset.SEMIANNUAL: "Semestral (6 meses)",
    DateRangePreset.ANNUAL: "Anual",
}

_SORT_LABELS = [
    ("Primera venta (más antigua primero)", ProfitSortOption.FIRST_SALE_ASC),
    ("Mayor vendido", ProfitSortOption.MOST_SOLD),
    ("Menor vendido", ProfitSortOption.LEAST_SOLD),
    ("Mayor utilidad", ProfitSortOption.HIGHEST_PROFIT),
    ("Menor utilidad", ProfitSortOption.LOWEST_PROFIT),
    ("Mayor ingreso", ProfitSortOption.HIGHEST_REVENUE),
    ("Mayor cantidad", ProfitSortOption.HIGHEST_QUANTITY),
    ("Nombre A-Z", ProfitSortOption.NAME_ASC),
    ("Nombre Z-A", ProfitSortOption.NAME_DESC),
]

_TOP_LIST_LABELS = [
    ("Mayor utilidad", "highest_profit"),
    ("Menor utilidad", "lowest_profit"),
    ("Más vendidos", "most_sold"),
    ("Menos vendidos", "least_sold"),
    ("Mayor ingreso", "highest_revenue"),
    ("Menor ingreso", "lowest_revenue"),
]

_TABLE_HEIGHT = 420


class ProfitsTabView(QWidget):
    def __init__(
        self,
        preset: DateRangePreset,
        view_model: ProfitsViewModel,
        invoice_settings_service: InvoiceSettingsService,
        session_manager: SessionManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._preset = preset
        self._view_model = view_model
        self._invoice_settings_service = invoice_settings_service
        self._session_manager = session_manager
        self._loading_filters = False
        self._latest_chart_series: ChartSeriesDTO | None = None

        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    # -- construcción ----------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)

        layout.addWidget(self._build_filters_panel())
        layout.addLayout(self._build_kpi_row())
        layout.addLayout(self._build_toolbar())
        layout.addWidget(self._build_table_stack())
        layout.addWidget(self._build_top_lists_panel())
        layout.addWidget(self._build_charts_panel())

    def _build_filters_panel(self) -> QGroupBox:
        box = QGroupBox("Filtros", self)
        grid = QGridLayout(box)

        self._date_from_edit = QDateEdit(self)
        self._date_from_edit.setCalendarPopup(True)
        self._date_to_edit = QDateEdit(self)
        self._date_to_edit.setCalendarPopup(True)
        grid.addWidget(QLabel("Desde"), 0, 0)
        grid.addWidget(self._date_from_edit, 0, 1)
        grid.addWidget(QLabel("Hasta"), 0, 2)
        grid.addWidget(self._date_to_edit, 0, 3)

        self._category_combo = QComboBox(self)
        self._supplier_combo = QComboBox(self)
        self._warehouse_combo = QComboBox(self)
        grid.addWidget(QLabel("Categoría"), 1, 0)
        grid.addWidget(self._category_combo, 1, 1)
        grid.addWidget(QLabel("Proveedor"), 1, 2)
        grid.addWidget(self._supplier_combo, 1, 3)

        self._user_combo = QComboBox(self)
        self._cash_register_combo = QComboBox(self)
        self._customer_combo = QComboBox(self)
        grid.addWidget(QLabel("Bodega"), 2, 0)
        grid.addWidget(self._warehouse_combo, 2, 1)
        grid.addWidget(QLabel("Usuario"), 2, 2)
        grid.addWidget(self._user_combo, 2, 3)

        grid.addWidget(QLabel("Caja"), 3, 0)
        grid.addWidget(self._cash_register_combo, 3, 1)
        grid.addWidget(QLabel("Cliente"), 3, 2)
        grid.addWidget(self._customer_combo, 3, 3)

        self._code_edit = QLineEdit(self)
        self._code_edit.setPlaceholderText("Código de producto")
        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("Nombre de producto")
        grid.addWidget(self._code_edit, 4, 1)
        grid.addWidget(self._name_edit, 4, 3)

        self._only_profit_check = QCheckBox("Solo productos con ganancias", self)
        self._only_loss_check = QCheckBox("Solo productos con pérdidas", self)
        self._sort_combo = QComboBox(self)
        for label, _option in _SORT_LABELS:
            self._sort_combo.addItem(label)
        grid.addWidget(self._only_profit_check, 5, 0, 1, 2)
        grid.addWidget(self._only_loss_check, 5, 2, 1, 2)
        grid.addWidget(QLabel("Ordenar por"), 6, 0)
        grid.addWidget(self._sort_combo, 6, 1)

        return box

    def _build_kpi_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._kpi_total_revenue = KpiCard("Total vendido", "$0")
        self._kpi_total_quantity = KpiCard("Cantidad vendida", "0")
        self._kpi_invoice_count = KpiCard("N.º de facturas", "0")
        self._kpi_total_cost = KpiCard("Costo total", "$0")
        self._kpi_total_profit = KpiCard("Ganancia total", "$0", value_role="success")
        self._kpi_avg_margin = KpiCard("Margen promedio", "0%")
        for card in (
            self._kpi_total_revenue,
            self._kpi_total_quantity,
            self._kpi_invoice_count,
            self._kpi_total_cost,
            self._kpi_total_profit,
            self._kpi_avg_margin,
        ):
            row.addWidget(card)
        return row

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._search_bar = SearchBar("Buscar por código, nombre, categoría o proveedor...", self)
        row.addWidget(self._search_bar, stretch=1)

        self._group_by_category_button = QPushButton("Agrupar por categoría", self)
        self._group_by_category_button.setCheckable(True)
        row.addWidget(self._group_by_category_button)

        self._refresh_button = QPushButton("Actualizar", self)
        self._pdf_button = QPushButton("Exportar PDF", self)
        self._excel_button = QPushButton("Exportar Excel", self)
        self._print_button = QPushButton("Imprimir", self)
        self._copy_button = QPushButton("Copiar al portapapeles", self)
        for button in (
            self._refresh_button,
            self._pdf_button,
            self._excel_button,
            self._print_button,
            self._copy_button,
        ):
            row.addWidget(button)
        return row

    def _build_table_stack(self) -> QStackedWidget:
        self._table_stack = QStackedWidget(self)

        self._source_model = ProfitProductTableModel(self)
        self._proxy_model = SearchFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        self._table = QTableView(self)
        self._table.setModel(self._proxy_model)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setMinimumSectionSize(110)
        self._table.setMinimumHeight(_TABLE_HEIGHT)
        self._table.setMaximumHeight(_TABLE_HEIGHT)
        self._table.doubleClicked.connect(self._on_table_double_clicked)
        self._table_stack.addWidget(self._table)

        self._category_model = CategoryProfitTableModel(self)
        self._category_table = QTableView(self)
        self._category_table.setModel(self._category_model)
        self._category_table.setSortingEnabled(True)
        self._category_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._category_table.setMinimumHeight(_TABLE_HEIGHT)
        self._category_table.setMaximumHeight(_TABLE_HEIGHT)
        self._table_stack.addWidget(self._category_table)

        return self._table_stack

    def _build_top_lists_panel(self) -> QGroupBox:
        box = QGroupBox("Top 10", self)
        layout = QVBoxLayout(box)
        self._top_list_combo = QComboBox(self)
        for label, _key in _TOP_LIST_LABELS:
            self._top_list_combo.addItem(label)
        layout.addWidget(self._top_list_combo)
        self._top_list_widget = QListWidget(self)
        layout.addWidget(self._top_list_widget)
        return box

    def _build_charts_panel(self) -> QWidget:
        container = QWidget(self)
        grid = QGridLayout(container)

        self._pie_chart = SimplePieChart(self)
        grid.addWidget(self._chart_box("Productos más vendidos", self._pie_chart), 0, 0)

        self._bar_chart = SimpleBarChart(self)
        grid.addWidget(self._chart_box("Ganancias por categoría", self._bar_chart), 0, 1)

        self._line_chart = SimpleLineChart(self)
        grid.addWidget(self._chart_box("Evolución diaria de ingresos", self._line_chart), 1, 0)

        self._area_chart = SimpleAreaChart(self)
        grid.addWidget(self._chart_box("Ganancia acumulada", self._area_chart), 1, 1)

        return container

    def _chart_box(self, title: str, chart: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(make_section_title(title))
        layout.addWidget(chart)
        export_button = QPushButton("Exportar imagen", box)
        export_button.clicked.connect(lambda: self._export_chart_image(chart))
        layout.addWidget(export_button)
        return box

    # -- señales -----------------------------------------------------------

    def _connect_signals(self) -> None:
        self._view_model.filter_options_loaded.connect(self._on_filter_options_loaded)
        self._view_model.summary_loaded.connect(self._on_summary_loaded)
        self._view_model.rows_loaded.connect(self._on_rows_loaded)
        self._view_model.category_groups_loaded.connect(self._on_category_groups_loaded)
        self._view_model.top_lists_loaded.connect(self._on_top_lists_loaded)
        self._view_model.chart_series_loaded.connect(self._on_chart_series_loaded)
        self._view_model.history_loaded.connect(self._on_history_loaded)
        self._view_model.date_range_changed.connect(self._on_date_range_changed)
        self._view_model.error_occurred.connect(self._show_error)

        for combo in (
            self._category_combo,
            self._supplier_combo,
            self._warehouse_combo,
            self._user_combo,
            self._cash_register_combo,
            self._customer_combo,
            self._sort_combo,
        ):
            combo.currentIndexChanged.connect(self._on_filters_changed)
        self._code_edit.textChanged.connect(self._on_filters_changed)
        self._name_edit.textChanged.connect(self._on_filters_changed)
        self._only_profit_check.toggled.connect(self._on_filters_changed)
        self._only_loss_check.toggled.connect(self._on_filters_changed)
        self._date_from_edit.dateChanged.connect(self._on_date_edits_changed)
        self._date_to_edit.dateChanged.connect(self._on_date_edits_changed)

        self._search_bar.text_changed.connect(self._proxy_model.set_search_text)
        self._group_by_category_button.toggled.connect(self._on_group_by_category_toggled)
        self._refresh_button.clicked.connect(self._view_model.refresh)
        self._pdf_button.clicked.connect(self._on_export_pdf_clicked)
        self._excel_button.clicked.connect(self._on_export_excel_clicked)
        self._print_button.clicked.connect(self._on_print_clicked)
        self._copy_button.clicked.connect(self._on_copy_clicked)
        self._top_list_combo.currentIndexChanged.connect(self._render_top_list)

    # -- carga de datos ------------------------------------------------

    def _on_filter_options_loaded(
        self,
        categories: list[CategoryDTO],
        suppliers: list[SupplierDTO],
        warehouses: list[WarehouseDTO],
        users: list[UserDTO],
        cash_registers: list[CashRegisterDTO],
        customers: list[CustomerDTO],
    ) -> None:
        self._loading_filters = True
        self._category_combo.clear()
        self._category_combo.addItem("(Todas)", None)
        for category in categories:
            self._category_combo.addItem(category.name, category.id)

        self._supplier_combo.clear()
        self._supplier_combo.addItem("(Todos)", None)
        for supplier in suppliers:
            self._supplier_combo.addItem(supplier.company_name, supplier.id)

        self._warehouse_combo.clear()
        self._warehouse_combo.addItem("(Todas)", None)
        for warehouse in warehouses:
            self._warehouse_combo.addItem(warehouse.name, warehouse.id)

        self._user_combo.clear()
        self._user_combo.addItem("(Todos)", None)
        for user in users:
            self._user_combo.addItem(user.full_name, user.id)

        self._cash_register_combo.clear()
        self._cash_register_combo.addItem("(Todas)", None)
        for register in cash_registers:
            self._cash_register_combo.addItem(register.name, register.id)

        self._customer_combo.clear()
        self._customer_combo.addItem("(Todos)", None)
        for customer in customers:
            self._customer_combo.addItem(customer.full_name, customer.id)
        self._loading_filters = False

    def _on_date_range_changed(self, date_from: date_, date_to: date_) -> None:
        self._loading_filters = True
        self._date_from_edit.setDate(QDate(date_from.year, date_from.month, date_from.day))
        self._date_to_edit.setDate(QDate(date_to.year, date_to.month, date_to.day))
        self._loading_filters = False

    def _on_date_edits_changed(self) -> None:
        if self._loading_filters:
            return
        qdate_from = self._date_from_edit.date()
        qdate_to = self._date_to_edit.date()
        self._view_model.set_date_range(
            date_(qdate_from.year(), qdate_from.month(), qdate_from.day()),
            date_(qdate_to.year(), qdate_to.month(), qdate_to.day()),
        )

    def _on_filters_changed(self) -> None:
        if self._loading_filters:
            return
        filters = ProfitFilters(
            category_id=self._category_combo.currentData(),
            supplier_id=self._supplier_combo.currentData(),
            warehouse_id=self._warehouse_combo.currentData(),
            user_id=self._user_combo.currentData(),
            cash_register_id=self._cash_register_combo.currentData(),
            customer_id=self._customer_combo.currentData(),
            product_code=self._code_edit.text().strip() or None,
            product_name=self._name_edit.text().strip() or None,
            only_with_profit=self._only_profit_check.isChecked(),
            only_with_loss=self._only_loss_check.isChecked(),
            sort=_SORT_LABELS[self._sort_combo.currentIndex()][1],
        )
        self._view_model.set_filters(filters)

    def _on_summary_loaded(self, summary: ProfitSummaryDTO) -> None:
        self._kpi_total_revenue.set_value(format_currency(summary.total_revenue))
        self._kpi_total_quantity.set_value(format_quantity(summary.total_quantity, None))
        self._kpi_invoice_count.set_value(str(summary.invoice_count))
        self._kpi_total_cost.set_value(
            "N/D" if summary.total_cost is None else format_currency(summary.total_cost)
        )
        self._kpi_total_profit.set_value(
            "N/D" if summary.total_profit is None else format_currency(summary.total_profit)
        )
        self._kpi_avg_margin.set_value(
            "N/D" if summary.avg_margin_pct is None else f"{summary.avg_margin_pct:g}%"
        )

    def _on_rows_loaded(self, rows: list[ProductProfitRowDTO]) -> None:
        self._source_model.set_rows(rows)

    def _on_category_groups_loaded(self, groups) -> None:  # noqa: ANN001
        self._category_model.set_rows(groups)

    def _on_top_lists_loaded(self, top_lists: TopListsDTO) -> None:
        self._latest_top_lists = top_lists
        self._render_top_list()

    def _render_top_list(self) -> None:
        if not hasattr(self, "_latest_top_lists"):
            return
        key = _TOP_LIST_LABELS[self._top_list_combo.currentIndex()][1]
        entries = getattr(self._latest_top_lists, key)
        self._top_list_widget.clear()
        for rank, entry in enumerate(entries, start=1):
            self._top_list_widget.addItem(f"{rank}. {entry.label} — {entry.value:,.2f}")

    def _on_chart_series_loaded(self, series: ChartSeriesDTO) -> None:
        self._latest_chart_series = series
        self._pie_chart.set_data(
            [PieChartSlice(label=e.label, value=e.value) for e in series.top_products_by_quantity]
        )
        self._bar_chart.set_data(
            [
                ChartSeriesPoint(
                    label=group.category_name,
                    sales_total=group.total_revenue,
                    profit_total=group.total_profit or Decimal(0),
                )
                for group in series.profit_by_category
            ]
        )
        self._line_chart.set_data(
            [
                LineChartPoint(label=day.strftime("%d/%m"), value=value)
                for day, value in series.daily_revenue
            ]
        )
        self._area_chart.set_data(
            [
                AreaChartPoint(label=day.strftime("%d/%m"), value=value)
                for day, value in series.cumulative_profit
            ]
        )

    def _on_group_by_category_toggled(self, checked: bool) -> None:
        self._table_stack.setCurrentIndex(1 if checked else 0)

    # -- drill-down --------------------------------------------------------

    def _on_table_double_clicked(self, index: QModelIndex) -> None:
        source_row = self._proxy_model.mapToSource(index).row()
        row = self._source_model.row_at(source_row)
        self._history_dialog = ProductSaleHistoryDialog(row.product_name, self)
        self._view_model.load_history(row.product_id)
        self._history_dialog.exec()

    def _on_history_loaded(self, entries) -> None:  # noqa: ANN001
        if hasattr(self, "_history_dialog"):
            self._history_dialog.set_entries(entries)

    # -- exportación ---------------------------------------------------

    def _period_label(self) -> str:
        date_from, date_to = self._view_model.date_range()
        return f"{_PRESET_LABELS[self._preset]}: {date_from} a {date_to}"

    def _filters_description(self) -> str:
        parts = []
        if self._category_combo.currentData() is not None:
            parts.append(f"Categoría={self._category_combo.currentText()}")
        if self._supplier_combo.currentData() is not None:
            parts.append(f"Proveedor={self._supplier_combo.currentText()}")
        if self._warehouse_combo.currentData() is not None:
            parts.append(f"Bodega={self._warehouse_combo.currentText()}")
        if self._user_combo.currentData() is not None:
            parts.append(f"Usuario={self._user_combo.currentText()}")
        if self._cash_register_combo.currentData() is not None:
            parts.append(f"Caja={self._cash_register_combo.currentText()}")
        if self._customer_combo.currentData() is not None:
            parts.append(f"Cliente={self._customer_combo.currentText()}")
        return "; ".join(parts) if parts else "Sin filtros"

    def _current_user_name(self) -> str:
        session = self._session_manager.current
        return session.full_name if session else "—"

    def _on_export_excel_clicked(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar a Excel", "ganancias.xlsx", "*.xlsx"
        )
        if not file_path:
            return
        self._view_model.export_to_excel(Path(file_path), self._period_label())
        self._show_info("Excel exportado correctamente.")

    def _on_export_pdf_clicked(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar a PDF", "ganancias.pdf", "*.pdf"
        )
        if not file_path:
            return
        self._export_pdf_to(Path(file_path))
        self._show_info("PDF exportado correctamente.")

    def _export_pdf_to(self, file_path: Path) -> None:
        settings = self._invoice_settings_service.get_settings()
        self._view_model.export_to_pdf(
            file_path,
            company_name=settings.company_name,
            logo_path=settings.logo_path,
            generated_by=self._current_user_name(),
            period_label=self._period_label(),
            filters_description=self._filters_description(),
        )

    def _on_print_clicked(self) -> None:
        temp_dir = Path(tempfile.gettempdir())
        temp_path = temp_dir / "ganancias_impresion.pdf"
        self._export_pdf_to(temp_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(temp_path)))

    def _on_copy_clicked(self) -> None:
        header = [
            str(self._source_model.headerData(c, Qt.Orientation.Horizontal) or "")
            for c in range(self._proxy_model.columnCount())
        ]
        lines = ["\t".join(header)]
        for row in range(self._proxy_model.rowCount()):
            values = []
            for column in range(self._proxy_model.columnCount()):
                index = self._proxy_model.index(row, column)
                values.append(str(self._proxy_model.data(index) or ""))
            lines.append("\t".join(values))
        QApplication.clipboard().setText("\n".join(lines))
        self._show_info("Tabla copiada al portapapeles.")

    def _export_chart_image(self, chart) -> None:  # noqa: ANN001
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar gráfico", "grafico.png", "*.png"
        )
        if not file_path:
            return
        chart.export_to_png(Path(file_path))

    # -- utilidades ------------------------------------------------------

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
