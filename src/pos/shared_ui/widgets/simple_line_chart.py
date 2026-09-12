"""Gráfica de línea liviana dibujada con `QPainter` — mismo enfoque que
`simple_bar_chart.py::SimpleBarChart` (sin librería de gráficos nueva).
Usada por Ganancias para la evolución diaria de ingresos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from pos.shared_ui.theme.theme_manager import get_active_tokens

_MARGIN_BOTTOM = 30
_MARGIN_TOP = 12
_MARGIN_SIDE = 12
_POINT_RADIUS = 3.0
_MAX_LABELS = 8


@dataclass(frozen=True)
class LineChartPoint:
    label: str
    value: Decimal


class SimpleLineChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: list[LineChartPoint] = []
        self.setMinimumHeight(240)

    def set_data(self, points: list[LineChartPoint]) -> None:
        self._points = points
        self.update()

    def export_to_png(self, path: Path) -> None:
        self.grab().save(str(path), "PNG")

    def _plot_points(self) -> tuple[list[QPointF], Decimal]:
        chart_width = self.width() - 2 * _MARGIN_SIDE
        chart_height = self.height() - _MARGIN_BOTTOM - _MARGIN_TOP
        max_value = max((p.value for p in self._points), default=Decimal(0))
        if max_value <= 0:
            max_value = Decimal(1)
        count = len(self._points)
        step = chart_width / max(count - 1, 1)
        plotted = []
        for index, point in enumerate(self._points):
            x = _MARGIN_SIDE + index * step
            y = _MARGIN_TOP + chart_height - float(point.value / max_value) * chart_height
            plotted.append(QPointF(x, y))
        return plotted, max_value

    def paintEvent(self, event: object) -> None:  # noqa: N802 (nombre de Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._points:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos para mostrar")
            painter.end()
            return

        line_color = QColor(get_active_tokens().primary)
        plotted, _ = self._plot_points()
        painter.setPen(QPen(line_color, 2))
        for a, b in zip(plotted, plotted[1:], strict=False):
            painter.drawLine(a, b)

        painter.setBrush(line_color)
        painter.setPen(Qt.PenStyle.NoPen)
        for point in plotted:
            painter.drawEllipse(point, _POINT_RADIUS, _POINT_RADIUS)

        label_step = max(len(self._points) // _MAX_LABELS, 1)
        painter.setPen(self.palette().windowText().color())
        for index, point in enumerate(self._points):
            if index % label_step != 0:
                continue
            x = plotted[index].x()
            painter.drawText(
                QRectF(x - 30, self.height() - _MARGIN_BOTTOM, 60, _MARGIN_BOTTOM),
                Qt.AlignmentFlag.AlignCenter,
                point.label,
            )
        painter.end()
