"""Historial de conexiones/errores/diagnóstico de una báscula
(Administración → Dispositivos → Báscula electrónica)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.scales.application.dto import ScaleDeviceEventDTO
from pos.modules.scales.domain.enums import ScaleDeviceEventType

_COLUMNS = ["Fecha y hora", "Evento", "Detalle"]
_EVENT_LABELS: dict[ScaleDeviceEventType, str] = {
    ScaleDeviceEventType.CONNECTED: "Conectada",
    ScaleDeviceEventType.DISCONNECTED: "Desconectada",
    ScaleDeviceEventType.ERROR: "Error",
    ScaleDeviceEventType.READ_SUCCESS: "Lectura exitosa",
    ScaleDeviceEventType.READ_FAILED: "Lectura fallida",
    ScaleDeviceEventType.TARE: "Tara",
    ScaleDeviceEventType.CALIBRATION: "Calibración",
    ScaleDeviceEventType.TEST_CONNECTION_OK: "Prueba de conexión exitosa",
    ScaleDeviceEventType.TEST_CONNECTION_FAILED: "Prueba de conexión fallida",
}


class ScaleDeviceHistoryDialog(QDialog):
    def __init__(
        self, events: list[ScaleDeviceEventDTO], device_name: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Historial — {device_name}")
        self.setMinimumSize(520, 360)
        layout = QVBoxLayout(self)

        table = QTableWidget(len(events), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, event in enumerate(events):
            table.setItem(row, 0, QTableWidgetItem(f"{event.occurred_at.astimezone():%Y-%m-%d %H:%M:%S}"))
            table.setItem(row, 1, QTableWidgetItem(_EVENT_LABELS.get(event.event_type, event.event_type.value)))
            table.setItem(row, 2, QTableWidgetItem(event.message or ""))
        layout.addWidget(table)
