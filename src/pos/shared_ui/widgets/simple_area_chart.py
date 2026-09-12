"""Gráfica de área liviana dibujada con `QPainter` — mismo enfoque que
`simple_bar_chart.py::SimpleBarChart` (sin librería de gráficos nueva).
Usada por Ganancias para la ganancia acumulada del período."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from pos.shared_ui.theme.theme_manager import get_active_tokens

_MARGIN_BOTTOM = 30
_MARGIN_TOP = 12
_MARGIN_SIDE = 12
_FILL_ALPHA = 60
_MAX_LABELS = 8


@dataclass(frozen=True)
class AreaChartPoint:
    label: str
    value: Decimal


class SimpleAreaChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: list[AreaChartPoint] = []
        self.setMinimumHeight(240)

    def set_data(self, points: list[AreaChartPoint]) -> None:
        self._points = points
        self.update()

    def export_to_png(self, path: Path) -> None:
        self.grab().save(str(path), "PNG")

    def paintEvent(self, event: object) -> None:  # noqa: N802 (nombre de Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._points:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos para mostrar")
            painter.end()
            return

        chart_width = self.width() - 2 * _MARGIN_SIDE
        chart_height = self.height() - _MARGIN_BOTTOM - _MARGIN_TOP
        values = [p.value for p in self._points]
        max_value = max(max(values, default=Decimal(0)), Decimal(0))
        min_value = min(min(values, default=Decimal(0)), Decimal(0))
        value_range = max_value - min_value if max_value != min_value else Decimal(1)

        count = len(self._points)
        step = chart_width / max(count - 1, 1)

        def _y_for(value: Decimal) -> float:
            fraction = float((value - min_value) / value_range)
            return _MARGIN_TOP + chart_height - fraction * chart_height

        baseline_y = _y_for(Decimal(0))
        plotted = []
        for index, point in enumerate(self._points):
            x = _MARGIN_SIDE + index * step
            plotted.append(QPointF(x, _y_for(point.value)))

        line_color = QColor(get_active_tokens().success)
        fill_color = QColor(line_color)
        fill_color.setAlpha(_FILL_ALPHA)

        polygon = QPolygonF(
            [QPointF(plotted[0].x(), baseline_y), *plotted, QPointF(plotted[-1].x(), baseline_y)]
        )
        painter.setBrush(fill_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(polygon)

        painter.setPen(QPen(line_color, 2))
        for a, b in zip(plotted, plotted[1:], strict=False):
            painter.drawLine(a, b)

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
