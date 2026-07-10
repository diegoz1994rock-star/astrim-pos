"""View model de la pantalla de reportes."""

from __future__ import annotations

import enum
from datetime import date
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pos.modules.reports.application.reports_service import ReportsService
from pos.modules.reports.domain.enums import ReportFormat


class ReportKind(enum.Enum):
    SALES = "Ventas"
    PRODUCTS = "Productos"
    INVENTORY = "Inventario"
    CASH = "Caja"


class ReportsViewModel(QObject):
    report_ready = Signal(list, list)
    """Emite `(headers, rows)` listos para mostrar en una tabla o exportar."""
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, reports_service: ReportsService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._reports_service = reports_service
        self._last_headers: list[str] = []
        self._last_rows: list[list[str]] = []
        self._last_title = ""

    def generate(self, kind: ReportKind, date_from: date, date_to: date) -> None:
        if kind is ReportKind.SALES:
            sales_report = self._reports_service.sales_report(date_from, date_to)
            headers = ["Venta #", "Fecha", "Estado", "Cliente", "Total"]
            rows = [
                [
                    str(r.sale_id),
                    f"{r.created_at:%Y-%m-%d %H:%M}",
                    r.status,
                    r.customer_name,
                    f"{r.total:.2f}",
                ]
                for r in sales_report.rows
            ]
            title = f"Ventas {date_from} a {date_to} (total: {sales_report.total_amount:.2f})"
        elif kind is ReportKind.PRODUCTS:
            products_report = self._reports_service.product_sales_report(date_from, date_to)
            headers = ["SKU", "Producto", "Cantidad vendida", "Ingreso"]
            rows = [
                [r.sku, r.product_name, str(r.quantity_sold), f"{r.revenue:.2f}"]
                for r in products_report.rows
            ]
            title = f"Productos vendidos {date_from} a {date_to}"
        elif kind is ReportKind.INVENTORY:
            inv_report = self._reports_service.inventory_report()
            headers = ["SKU", "Producto", "Bodega", "Cantidad", "Mínimo"]
            rows = [
                [r.sku, r.product_name, r.warehouse_name, str(r.quantity), str(r.min_quantity)]
                for r in inv_report.rows
            ]
            title = "Inventario actual"
        else:
            cash_report = self._reports_service.cash_report(date_from, date_to)
            headers = ["Sesión #", "Caja", "Apertura", "Cierre", "Diferencia"]
            rows = [
                [
                    str(r.session_id),
                    r.register_name,
                    f"{r.opening_amount:.2f}",
                    f"{r.closing_amount:.2f}" if r.closing_amount is not None else "(abierta)",
                    f"{r.difference:.2f}" if r.difference is not None else "-",
                ]
                for r in cash_report.rows
            ]
            title = f"Caja {date_from} a {date_to}"

        self._last_headers = headers
        self._last_rows = rows
        self._last_title = title
        self.report_ready.emit(headers, rows)

    def export(self, report_format: ReportFormat, file_path: Path) -> None:
        if not self._last_headers:
            self.error_occurred.emit("Genera un reporte antes de exportarlo.")
            return
        self._reports_service.export(
            title=self._last_title,
            headers=self._last_headers,
            rows=self._last_rows,
            file_path=file_path,
            report_format=report_format,
        )
        self.operation_succeeded.emit(f"Reporte exportado a {file_path}.")
