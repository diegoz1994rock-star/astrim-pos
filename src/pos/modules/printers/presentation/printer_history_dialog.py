"""Historial de auditoría de una impresora — conexiones/errores y, sobre
todo, cada documento impreso (factura, recibo de abono, página de prueba)
con su contexto completo: usuario, caja, documento, resultado, tiempo de
respuesta."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.printers.application.dto import PrinterEventDTO
from pos.modules.printers.domain.enums import PrintDocumentType, PrinterEventType

_COLUMNS = [
    "Fecha y hora", "Evento", "Usuario", "Caja", "Tipo de documento",
    "Referencia", "Venta", "Factura", "Tiempo", "Detalle",
]
_EVENT_LABELS: dict[PrinterEventType, str] = {
    PrinterEventType.CONNECTED: "Conectada",
    PrinterEventType.DISCONNECTED: "Desconectada",
    PrinterEventType.ERROR: "Error",
    PrinterEventType.TEST_CONNECTION_OK: "Prueba de conexión exitosa",
    PrinterEventType.TEST_CONNECTION_FAILED: "Prueba de conexión fallida",
    PrinterEventType.TEST_PAGE_PRINTED: "Página de prueba impresa",
    PrinterEventType.TEST_PAGE_FAILED: "Página de prueba fallida",
    PrinterEventType.PRINT_SUCCESS: "Impresión correcta",
    PrinterEventType.PRINT_FAILED: "Impresión fallida",
}
_DOCUMENT_TYPE_LABELS: dict[PrintDocumentType, str] = {
    PrintDocumentType.INVOICE: "Factura",
    PrintDocumentType.DEBT_RECEIPT: "Recibo de abono",
    PrintDocumentType.TEST_PAGE: "Página de prueba",
}


class PrinterHistoryDialog(QDialog):
    def __init__(
        self, events: list[PrinterEventDTO], device_name: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Historial — {device_name}")
        self.resize(1100, 420)
        layout = QVBoxLayout(self)

        table = QTableWidget(len(events), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for row, event in enumerate(events):
            values = [
                f"{event.occurred_at.astimezone():%Y-%m-%d %H:%M:%S}",
                _EVENT_LABELS.get(event.event_type, event.event_type.value),
                event.username or "—",
                event.cash_register_name or "—",
                _DOCUMENT_TYPE_LABELS.get(event.document_type, "—")
                if event.document_type
                else "—",
                event.document_reference or "—",
                str(event.sale_id) if event.sale_id else "—",
                str(event.invoice_id) if event.invoice_id else "—",
                f"{event.duration_ms} ms" if event.duration_ms is not None else "—",
                event.message or "",
            ]
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table)
