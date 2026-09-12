"""Mini-gráfico de tendencia ("sparkline") para el pie de una `KpiCard` —
sin ejes, etiquetas ni márgenes de `SimpleLineChart` (ese widget está
pensado para la pantalla de Reportes, con `setMinimumHeight(240)`; acá el
espacio disponible es de ~28px dentro de una tarjeta). Mismo enfoque
`QPainter` liviano que el resto de `shared_ui/widgets/simple_*_chart.py`,
sin librería de gráficos nueva."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

_HEIGHT_PX = 28
_POINT_RADIUS = 2.5
_LINE_WIDTH = 1.8


class Sparkline(QWidget):
    def __init__(self, color_hex: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color_hex)
        self._values: list[Decimal] = []
        self.setFixedHeight(_HEIGHT_PX)

    def set_data(self, values: list[Decimal]) -> None:
        self._values = values
        self.update()

    def _plot_points(self) -> list[QPointF]:
        width = self.width()
        height = self.height() - _POINT_RADIUS
        max_value = max(self._values, default=Decimal(0))
        min_value = min(self._values, default=Decimal(0))
        value_range = max_value - min_value or Decimal(1)
        count = len(self._values)
        step = width / max(count - 1, 1)
        points = []
        for index, value in enumerate(self._values):
            x = index * step
            ratio = float((value - min_value) / value_range)
            y = _POINT_RADIUS + (1 - ratio) * (height - _POINT_RADIUS)
            points.append(QPointF(x, y))
        return points

    def paintEvent(self, event: object) -> None:  # noqa: N802 (nombre de Qt)
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        points = self._plot_points()

        fill_path = QPainterPath(points[0])
        for point in points[1:]:
            fill_path.lineTo(point)
        fill_path.lineTo(points[-1].x(), self.height())
        fill_path.lineTo(points[0].x(), self.height())
        fill_path.closeSubpath()

        gradient = QLinearGradient(0, 0, 0, self.height())
        fill_color = QColor(self._color)
        fill_color.setAlphaF(0.22)
        gradient.setColorAt(0.0, fill_color)
        fill_color.setAlphaF(0.0)
        gradient.setColorAt(1.0, fill_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(fill_path)

        painter.setPen(QPen(self._color, _LINE_WIDTH))
        for a, b in zip(points, points[1:], strict=False):
            painter.drawLine(a, b)

        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(points[-1], _POINT_RADIUS, _POINT_RADIUS)
        painter.end()
