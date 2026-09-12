"""Diálogo "Diagnóstico" global de básculas — agrega todas las pesadas
reales (Ventas, panel de pruebas), sin requerir ningún dispositivo puntual
seleccionado. Equivalente de `BarcodeDiagnosticsDialog`."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.shared_ui.formatting import format_datetime_local


class ScaleDiagnosticsDialog(QDialog):
    def __init__(
        self,
        scale_read_service: ScaleReadService,
        device_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico de la báscula")
        self.setMinimumWidth(420)

        diagnostics = scale_read_service.get_diagnostics(device_id)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        status_label = QLabel("Conectada" if diagnostics.connected else "Desconectada")
        status_label.setProperty("role", "success" if diagnostics.connected else "secondary")
        form.addRow("Estado:", status_label)
        form.addRow("Puerto:", QLabel(diagnostics.port or "—"))
        form.addRow(
            "Velocidad:",
            QLabel(str(diagnostics.baud_rate) if diagnostics.baud_rate else "—"),
        )
        form.addRow(
            "Peso actual:",
            QLabel(
                str(diagnostics.current_weight) if diagnostics.current_weight is not None else "—"
            ),
        )
        form.addRow(
            "Último peso:",
            QLabel(str(diagnostics.last_weight) if diagnostics.last_weight is not None else "—"),
        )
        form.addRow(
            "Última lectura:",
            QLabel(
                format_datetime_local(diagnostics.last_read_at, "%Y-%m-%d %H:%M:%S")
                if diagnostics.last_read_at is not None
                else "—"
            ),
        )
        form.addRow("Último error:", QLabel(diagnostics.last_error or "—"))
        form.addRow("Cantidad de lecturas:", QLabel(str(diagnostics.total_reads)))
        form.addRow("Cantidad de errores:", QLabel(str(diagnostics.error_count)))
        form.addRow("Reconexiones:", QLabel(str(diagnostics.reconnection_count)))
        form.addRow(
            "Tiempo promedio de lectura:",
            QLabel(
                f"{diagnostics.average_read_duration_ms:.0f} ms"
                if diagnostics.average_read_duration_ms is not None
                else "—"
            ),
        )
        form.addRow(
            "Tiempo activo:",
            QLabel(
                f"{diagnostics.uptime_seconds:.0f} s"
                if diagnostics.uptime_seconds is not None
                else "—"
            ),
        )
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
