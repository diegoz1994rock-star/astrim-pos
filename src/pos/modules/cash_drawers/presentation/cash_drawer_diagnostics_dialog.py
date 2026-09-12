"""Diagnóstico de un cajón monedero — mismo espíritu que
`scale_diagnostics_dialog.py`/`barcode_scanner_diagnostics_dialog.py`: estado,
puerto, adaptador ("driver"), marca/modelo, última apertura, tiempo de
respuesta promedio, cantidad de aperturas y errores, sin requerir hardware
conectado para poder abrirlo."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_drawers.application.providers.registry import DRAWER_KIND_LABELS
from pos.shared_ui.formatting import format_datetime_local

_COMPATIBLE_CONNECTIONS = "USB, Puerto serial (COM/RS232), Ethernet/TCP-IP, vía datáfono enlazado"


class CashDrawerDiagnosticsDialog(QDialog):
    def __init__(
        self, service: CashDrawerService, device_id: int, device_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Diagnóstico — {device_name}")
        self.setMinimumWidth(420)

        diagnostics = service.get_diagnostics(device_id)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        status_label = QLabel("Conectado" if diagnostics.connected else "Desconectado")
        status_label.setProperty("role", "success" if diagnostics.connected else "secondary")
        form.addRow("Estado:", status_label)
        form.addRow("Puerto:", QLabel(diagnostics.port or "—"))
        ip_text = (
            f"{diagnostics.ip_address}:{diagnostics.ip_port}"
            if diagnostics.ip_address
            else "—"
        )
        form.addRow("IP:", QLabel(ip_text))
        driver_label = DRAWER_KIND_LABELS.get(diagnostics.kind, diagnostics.kind)
        form.addRow("Driver/adaptador:", QLabel(driver_label))
        form.addRow("Marca:", QLabel(diagnostics.brand or "—"))
        form.addRow("Modelo:", QLabel(diagnostics.model or "—"))
        form.addRow(
            "Última apertura:",
            QLabel(
                format_datetime_local(diagnostics.last_opened_at, "%Y-%m-%d %H:%M:%S")
                if diagnostics.last_opened_at is not None
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
        form.addRow("Cantidad de aperturas:", QLabel(str(diagnostics.total_opens)))
        form.addRow("Cantidad de errores:", QLabel(str(diagnostics.error_count)))
        form.addRow("Último error:", QLabel(diagnostics.last_error or "—"))
        form.addRow("Compatibilidad:", QLabel(_COMPATIBLE_CONNECTIONS))
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
