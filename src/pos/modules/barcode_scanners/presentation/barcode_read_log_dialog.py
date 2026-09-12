"""Diálogo "Ver historial" — extracto de todas las lecturas reales
registradas por `BarcodeReadService` (Ventas, formulario de producto,
"Probar lector"), la más reciente primero."""

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

from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource
from pos.shared_ui.formatting import format_datetime_local
from pos.shared_ui.widgets.table_utils import fit_table_to_contents

_COLUMNS = ["Hora", "Código", "Producto", "Usuario", "Caja", "Origen"]

_SOURCE_LABELS = {
    BarcodeReadSource.SALE: "Venta",
    BarcodeReadSource.PRODUCT_FORM: "Formulario de producto",
    BarcodeReadSource.TEST_PANEL: "Probar lector",
}


class BarcodeReadLogDialog(QDialog):
    def __init__(
        self, barcode_read_service: BarcodeReadService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Historial de lecturas")
        self.resize(760, 480)

        entries = barcode_read_service.list_recent_reads()

        layout = QVBoxLayout(self)
        table = QTableWidget(len(entries), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, entry in enumerate(entries):
            product_label = (entry.product_name or "—") if entry.found else "No encontrado"
            values = [
                format_datetime_local(entry.occurred_at, "%Y-%m-%d %H:%M:%S"),
                entry.code,
                product_label,
                entry.username or "—",
                entry.cash_register_name or "—",
                _SOURCE_LABELS.get(entry.source, entry.source.value),
            ]
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        fit_table_to_contents(table)
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
