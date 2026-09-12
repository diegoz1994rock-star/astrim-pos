"""Diagnóstico de una impresora — mismo espíritu que
`cash_drawer_diagnostics_dialog.py`/`scale_diagnostics_dialog.py`: estado,
disponibilidad, puerto/IP, método de impresión, marca/modelo, último
documento impreso, tiempo de respuesta promedio, cantidad de impresiones y
errores. `online`/`sin papel` se muestran como "No disponible" cuando el
método de impresión no puede consultarlos de verdad (ver
`PrinterProvider.query_paper_status` — limitación real y documentada de
`SYSTEM_DRIVER`, nunca un estado inventado)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.printers.application.providers.registry import PRINT_METHOD_LABELS
from pos.shared_ui.formatting import format_datetime_local


def _tri_state_label(value: bool | None, *, true_text: str, false_text: str) -> str:
    if value is None:
        return "No disponible"
    return true_text if value else false_text


class PrinterDiagnosticsDialog(QDialog):
    def __init__(
        self, service: PrinterService, device_id: int, device_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Diagnóstico — {device_name}")
        self.setMinimumWidth(420)

        diagnostics = service.get_diagnostics(device_id)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        status_label = QLabel("Conectada" if diagnostics.connected else "Desconectada")
        status_label.setProperty("role", "success" if diagnostics.connected else "secondary")
        form.addRow("Estado:", status_label)
        form.addRow("Disponible:", QLabel("Sí" if diagnostics.available else "No"))
        form.addRow(
            "En línea:",
            QLabel(_tri_state_label(diagnostics.online, true_text="Sí", false_text="No")),
        )
        form.addRow(
            "Sin papel:",
            QLabel(_tri_state_label(diagnostics.out_of_paper, true_text="Sí", false_text="No")),
        )
        form.addRow("Puerto:", QLabel(diagnostics.port or "—"))
        form.addRow("IP:", QLabel(diagnostics.ip_address or "—"))
        form.addRow(
            "Impresora del sistema:", QLabel(diagnostics.system_printer_name or "—")
        )
        method_label = PRINT_METHOD_LABELS.get(
            diagnostics.print_method, diagnostics.print_method.value
        )
        form.addRow("Método de impresión:", QLabel(method_label))
        form.addRow("Marca:", QLabel(diagnostics.brand or "—"))
        form.addRow("Modelo:", QLabel(diagnostics.model or "—"))
        form.addRow(
            "Último documento impreso:",
            QLabel(
                format_datetime_local(diagnostics.last_print_at, "%Y-%m-%d %H:%M:%S")
                if diagnostics.last_print_at is not None
                else "—"
            ),
        )
        form.addRow(
            "Tiempo de respuesta promedio:",
            QLabel(
                f"{diagnostics.average_response_time_ms:.0f} ms"
                if diagnostics.average_response_time_ms is not None
                else "—"
            ),
        )
        form.addRow("Cantidad de impresiones:", QLabel(str(diagnostics.total_prints)))
        form.addRow("Cantidad de errores:", QLabel(str(diagnostics.error_count)))
        form.addRow("Último error:", QLabel(diagnostics.last_error or "—"))
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
