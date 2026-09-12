"""Historial de lecturas de un lector de códigos de barras: Hora/Código/
Tipo/Caja/Usuario/Resultado."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.barcode_scanners.application.dto import ScanHistoryEntryDTO
from pos.modules.barcode_scanners.domain.enums import ScanResult

_COLUMNS = ["Hora", "Código", "Tipo", "Caja", "Usuario", "Resultado"]
_RESULT_LABELS = {ScanResult.SUCCESS: "Exitosa", ScanResult.FAILED: "Fallida"}


class BarcodeScannerHistoryDialog(QDialog):
    def __init__(
        self,
        entries: list[ScanHistoryEntryDTO],
        cash_register_names: dict[int, str],
        device_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Historial de lecturas — {device_name}")
        self.setMinimumSize(620, 400)
        layout = QVBoxLayout(self)

        table = QTableWidget(len(entries), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, entry in enumerate(entries):
            register_name = cash_register_names.get(entry.cash_register_id or -1, "—")
            result_text = _RESULT_LABELS[entry.result]
            if entry.is_simulated:
                result_text += " (simulada)"
            when = f"{entry.occurred_at.astimezone():%Y-%m-%d %H:%M:%S}"
            table.setItem(row, 0, QTableWidgetItem(when))
            table.setItem(row, 1, QTableWidgetItem(entry.code))
            table.setItem(row, 2, QTableWidgetItem(entry.symbology.value))
            table.setItem(row, 3, QTableWidgetItem(register_name))
            table.setItem(row, 4, QTableWidgetItem(str(entry.user_id) if entry.user_id else "—"))
            table.setItem(row, 5, QTableWidgetItem(result_text))
        layout.addWidget(table)
