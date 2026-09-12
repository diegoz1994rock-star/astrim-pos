"""Diálogo "Historial de lecturas" — extracto de todas las pesadas reales
registradas por `ScaleReadService` (Ventas, panel de pruebas), la más
reciente primero. Equivalente de `BarcodeReadLogDialog`."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.domain.enums import WeightReadingStatus
from pos.shared_ui.formatting import format_datetime_local
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = [
    "Hora", "Báscula", "Producto", "Peso neto", "Estado", "Usuario", "Caja",
    "Duración", "Reconectada", "Error",
]

_STATUS_LABELS = {
    WeightReadingStatus.STABLE: "Estable",
    WeightReadingStatus.UNSTABLE: "Inestable",
    WeightReadingStatus.ZERO: "Cero",
    WeightReadingStatus.NEGATIVE: "Negativo",
    WeightReadingStatus.INVALID: "Inválido",
    WeightReadingStatus.OUT_OF_RANGE: "Fuera de rango",
}

_STATUS_ROLES = {
    WeightReadingStatus.STABLE: "success",
    WeightReadingStatus.UNSTABLE: "warning",
    WeightReadingStatus.ZERO: "secondary",
    WeightReadingStatus.NEGATIVE: "danger",
    WeightReadingStatus.INVALID: "danger",
    WeightReadingStatus.OUT_OF_RANGE: "danger",
}


class ScaleReadLogDialog(QDialog):
    def __init__(
        self,
        scale_read_service: ScaleReadService,
        device_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Historial de lecturas de peso")
        self.resize(860, 480)

        entries = scale_read_service.list_recent_reads(device_id)

        layout = QVBoxLayout(self)
        table = QTableWidget(len(entries), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, entry in enumerate(entries):
            net_label = (
                f"{entry.net_weight} {entry.unit.value}" if entry.net_weight is not None else "—"
            )
            status_column = 4
            values = [
                format_datetime_local(entry.occurred_at, "%Y-%m-%d %H:%M:%S"),
                entry.device_name or "—",
                entry.product_name or "—",
                net_label,
                _STATUS_LABELS.get(entry.status, entry.status.value),
                entry.username or "—",
                entry.cash_register_name or "—",
                f"{entry.duration_ms} ms" if entry.duration_ms is not None else "—",
                "Sí" if entry.reconnected else "No",
                entry.error_message or "—",
            ]
            for column, value in enumerate(values):
                if column == status_column:
                    role = _STATUS_ROLES.get(entry.status, "secondary")
                    table.setCellWidget(row, column, StatusBadge(value, role))
                    continue
                table.setItem(row, column, QTableWidgetItem(value))
        fit_table_to_contents(table)
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
