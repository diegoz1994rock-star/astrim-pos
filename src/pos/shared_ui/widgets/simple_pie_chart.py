"""Gráfica de pastel liviana dibujada con `QPainter` — mismo enfoque que
`simple_bar_chart.py::SimpleBarChart` (sin librería de gráficos nueva).
Usada por Ganancias para "productos más vendidos"."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

_MARGIN = 12
_LEGEND_WIDTH = 160
_PALETTE = [
    "#2F6FED",
    "#1E9E5A",
    "#F5A623",
    "#E8483F",
    "#8E44AD",
    "#16A2B8",
    "#D4AC0D",
    "#7F8C8D",
]


@dataclass(frozen=True)
class PieChartSlice:
    label: str
    value: Decimal


class SimplePieChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slices: list[PieChartSlice] = []
        self.setMinimumHeight(240)

    def set_data(self, slices: list[PieChartSlice]) -> None:
        self._slices = slices
        self.update()

    def export_to_png(self, path: Path) -> None:
        self.grab().save(str(path), "PNG")

    def paintEvent(self, event: object) -> None:  # noqa: N802 (nombre de Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        total = sum((s.value for s in self._slices), Decimal(0))
        if not self._slices or total <= 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos para mostrar")
            painter.end()
            return

        diameter = min(self.height() - 2 * _MARGIN, self.width() - _LEGEND_WIDTH - 2 * _MARGIN)
        diameter = max(diameter, 10)
        pie_rect = QRectF(_MARGIN, (self.height() - diameter) / 2, diameter, diameter)

        start_angle = 90 * 16
        for index, item in enumerate(self._slices):
            span = int(float(item.value / total) * 360 * 16)
            color = QColor(_PALETTE[index % len(_PALETTE)])
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(pie_rect, start_angle, -span)
            start_angle -= span

        legend_x = pie_rect.right() + 16
        legend_y = _MARGIN
        painter.setFont(self.font())
        for index, item in enumerate(self._slices):
            color = QColor(_PALETTE[index % len(_PALETTE)])
            swatch = QRectF(legend_x, legend_y + 2, 10, 10)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(swatch)
            pct = float(item.value / total) * 100
            painter.setPen(self.palette().windowText().color())
            painter.drawText(
                QPointF(legend_x + 16, legend_y + 11),
                f"{item.label} ({pct:.1f}%)",
            )
            legend_y += 20
        painter.end()
