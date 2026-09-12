"""Historial de auditoría de un cajón monedero — conexiones/errores y,
sobre todo, cada apertura real (automática o manual) con su contexto
completo: usuario, caja, computador, sucursal, venta/factura/abono
relacionado, motivo, resultado, tiempo de respuesta, puerto/IP y modelo."""

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

from pos.modules.cash_drawers.application.dto import CashDrawerEventDTO
from pos.modules.cash_drawers.domain.enums import CashDrawerEventType, CashDrawerOpeningKind

_COLUMNS = [
    "Fecha y hora", "Evento", "Tipo", "Usuario", "Caja", "Computador", "Sucursal",
    "Venta", "Factura", "Abono", "Motivo", "Puerto/IP", "Modelo", "Tiempo", "Detalle",
]
_EVENT_LABELS: dict[CashDrawerEventType, str] = {
    CashDrawerEventType.CONNECTED: "Conectado",
    CashDrawerEventType.DISCONNECTED: "Desconectado",
    CashDrawerEventType.ERROR: "Error",
    CashDrawerEventType.TEST_CONNECTION_OK: "Prueba de conexión exitosa",
    CashDrawerEventType.TEST_CONNECTION_FAILED: "Prueba de conexión fallida",
    CashDrawerEventType.OPENED: "Apertura correcta",
    CashDrawerEventType.OPEN_FAILED: "Apertura fallida",
}
_OPENING_KIND_LABELS: dict[CashDrawerOpeningKind, str] = {
    CashDrawerOpeningKind.AUTOMATIC: "Automática",
    CashDrawerOpeningKind.MANUAL: "Manual",
}


def _port_or_ip(event: CashDrawerEventDTO) -> str:
    if event.ip_address_used:
        if event.ip_port_used:
            return f"{event.ip_address_used}:{event.ip_port_used}"
        return event.ip_address_used
    return event.port_used or "—"


class CashDrawerHistoryDialog(QDialog):
    def __init__(
        self, events: list[CashDrawerEventDTO], device_name: str, parent: QWidget | None = None
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
                _OPENING_KIND_LABELS.get(event.opening_kind, "—") if event.opening_kind else "—",
                event.username or "—",
                event.cash_register_name or "—",
                event.workstation or "—",
                event.branch_location or "—",
                str(event.sale_id) if event.sale_id else "—",
                str(event.invoice_id) if event.invoice_id else "—",
                str(event.debt_payment_id) if event.debt_payment_id else "—",
                event.reason or "—",
                _port_or_ip(event),
                event.model_snapshot or "—",
                f"{event.response_time_ms} ms" if event.response_time_ms is not None else "—",
                event.message or "",
            ]
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table)
