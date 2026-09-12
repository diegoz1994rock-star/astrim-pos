"""Diálogo "Diagnóstico" global — a diferencia de
`barcode_scanner_diagnostics_dialog.py` (por-dispositivo, que sigue
existiendo para la sección secundaria de inventario), este no requiere
ningún lector registrado: agrega todas las lecturas reales de Ventas,
Productos y "Probar lector"."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.shared_ui.formatting import format_datetime_local


class BarcodeDiagnosticsDialog(QDialog):
    def __init__(
        self, barcode_read_service: BarcodeReadService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico del lector")
        self.setMinimumWidth(420)

        diagnostics = barcode_read_service.get_diagnostics()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Último código leído:", QLabel(diagnostics.last_code or "—"))
        form.addRow(
            "Hora:",
            QLabel(
                format_datetime_local(diagnostics.last_read_at, "%Y-%m-%d %H:%M:%S")
                if diagnostics.last_read_at is not None
                else "—"
            ),
        )
        form.addRow("Cantidad de lecturas:", QLabel(str(diagnostics.total_reads)))
        form.addRow("Cantidad de errores:", QLabel(str(diagnostics.error_count)))
        form.addRow(
            "Tiempo promedio entre lecturas:",
            QLabel(
                f"{diagnostics.average_interval_ms:.0f} ms"
                if diagnostics.average_interval_ms is not None
                else "—"
            ),
        )
        status_label = QLabel(
            "USB HID detectado" if diagnostics.has_recent_activity else "Sin actividad"
        )
        status_label.setProperty(
            "role", "success" if diagnostics.has_recent_activity else "secondary"
        )
        form.addRow("Estado del lector:", status_label)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
