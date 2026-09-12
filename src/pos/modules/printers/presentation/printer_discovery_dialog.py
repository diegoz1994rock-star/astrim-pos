"""Resultado de "Buscar impresoras" — lo que el sistema operativo ya
reconoce (`PrinterService.discover_printers`, vía `QPrinterInfo`). Cubre
USB/red/compartidas/Bluetooth ya instaladas o emparejadas en el SO; no hay
forma de "detectar" un puerto serie crudo sin abrirlo (mismo límite
honesto que báscula/cajón/código de barras)."""

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

from pos.modules.printers.application.dto import DetectedPrinterDTO

_COLUMNS = [
    "Nombre", "Marca / Modelo", "Predeterminada (SO)", "Remota", "Ubicación", "Ya registrada",
]


class PrinterDiscoveryDialog(QDialog):
    def __init__(self, detected: list[DetectedPrinterDTO], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Impresoras detectadas por el sistema")
        self.resize(820, 400)
        self._detected = detected
        self._selected_name: str | None = None

        layout = QVBoxLayout(self)
        self._table = QTableWidget(len(detected), len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, item in enumerate(detected):
            values = [
                item.name,
                item.make_and_model or "—",
                "Sí" if item.is_default else "",
                "Sí" if item.is_remote else "No",
                item.location or "—",
                "Sí" if item.already_registered else "No",
            ]
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(value))
        self._table.cellDoubleClicked.connect(lambda row, _col: self._select_row(row))
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_row(self, row: int) -> None:
        self._table.selectRow(row)
        self._on_accept()

    def _on_accept(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if selected_rows:
            self._selected_name = self._detected[selected_rows[0].row()].name
        self.accept()

    def selected_printer(self) -> DetectedPrinterDTO | None:
        if self._selected_name is None:
            return None
        return next((d for d in self._detected if d.name == self._selected_name), None)
