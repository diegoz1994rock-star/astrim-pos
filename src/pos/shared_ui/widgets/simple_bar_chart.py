"""Gráfica de barras liviana dibujada con `QPainter` — no hay ninguna
librería de gráficos en el proyecto (sin matplotlib/pyqtgraph), así que se
evita agregar una dependencia nueva solo para dos barras por período."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from pos.shared_ui.theme.theme_manager import get_active_tokens

_MARGIN_BOTTOM = 30
_MARGIN_TOP = 12


@dataclass(frozen=True)
class ChartSeriesPoint:
    label: str
    sales_total: Decimal
    profit_total: Decimal


class SimpleBarChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: list[ChartSeriesPoint] = []
        self.setMinimumHeight(240)

    def set_data(self, points: list[ChartSeriesPoint]) -> None:
        self._points = points
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802 (nombre de Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._points:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos para mostrar")
            painter.end()
            return

        tokens = get_active_tokens()
        sales_color = QColor(tokens.primary)
        profit_color = QColor(tokens.success)

        width = self.width()
        height = self.height()
        chart_height = height - _MARGIN_BOTTOM - _MARGIN_TOP
        max_value = max(
            (max(point.sales_total, point.profit_total) for point in self._points),
            default=Decimal(0),
        )
        if max_value <= 0:
            max_value = Decimal(1)

        group_width = width / len(self._points)
        bar_width = group_width / 3
        for index, point in enumerate(self._points):
            x0 = index * group_width
            sales_height = float(point.sales_total / max_value) * chart_height
            profit_height = float(point.profit_total / max_value) * chart_height
            painter.fillRect(
                QRectF(
                    x0 + bar_width * 0.5,
                    _MARGIN_TOP + chart_height - sales_height,
                    bar_width,
                    sales_height,
                ),
                sales_color,
            )
            painter.fillRect(
                QRectF(
                    x0 + bar_width * 1.7,
                    _MARGIN_TOP + chart_height - profit_height,
                    bar_width,
                    profit_height,
                ),
                profit_color,
            )
            painter.drawText(
                QRectF(x0, height - _MARGIN_BOTTOM, group_width, _MARGIN_BOTTOM),
                Qt.AlignmentFlag.AlignCenter,
                point.label,
            )
        painter.end()
