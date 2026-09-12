"""Detalle de un backup del historial (doble clic sobre una fila de
`BackupsView`) — solo lectura, no permite editar ni restaurar desde acá."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from pos.modules.backups.application.dto import BackupHistoryDTO
from pos.modules.backups.domain.enums import BackupOrigin
from pos.shared_ui.formatting import format_file_size

_ORIGIN_LABELS = {
    BackupOrigin.MANUAL: "Manual",
    BackupOrigin.SCHEDULED: "Automático",
    BackupOrigin.IMPORTED: "Importado",
}


class BackupDetailDialog(QDialog):
    def __init__(self, entry: BackupHistoryDTO, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Detalle del backup")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        file_name = Path(entry.file_path).name if entry.file_path else "N/D"
        local_started = entry.started_at.astimezone()

        form.addRow("Nombre del archivo:", QLabel(file_name))
        form.addRow("Ruta completa:", QLabel(entry.file_path or "N/D"))
        form.addRow("Fecha:", QLabel(local_started.strftime("%Y-%m-%d")))
        form.addRow("Hora:", QLabel(local_started.strftime("%H:%M:%S")))
        form.addRow("Versión del sistema:", QLabel(entry.app_version or "Desconocida"))
        form.addRow(
            "Peso:",
            QLabel(format_file_size(entry.size_bytes) if entry.size_bytes is not None else "N/D"),
        )
        form.addRow(
            "Usuario:", QLabel(entry.created_by_username or _ORIGIN_LABELS[entry.origin])
        )
        form.addRow("Estado:", QLabel(entry.status.value))
        form.addRow("Tipo:", QLabel(_ORIGIN_LABELS[entry.origin]))
        form.addRow(
            "Hash de verificación:", QLabel(entry.checksum_sha256 or "No disponible")
        )
        for row in range(form.rowCount()):
            value_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            widget = value_item.widget() if value_item is not None else None
            if isinstance(widget, QLabel):
                widget.setWordWrap(True)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
