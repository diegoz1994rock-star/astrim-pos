"""Diálogo de solo lectura: historial completo de movimientos de
inventario ("Movimientos"). Nunca permite editar ni borrar — es un visor
sobre lo que ya se registró con Entrada/Salida/Ajuste/Transferencia."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.inventory.application.dto import StockMovementDTO
from pos.modules.inventory.domain.enums import StockMovementType
from pos.shared_ui.widgets.section_title import make_section_title

_COLUMNS = [
    "Fecha",
    "Hora",
    "Usuario",
    "Producto",
    "Bodega",
    "Tipo",
    "Cantidad",
    "Documento",
    "Observación",
]

_MOVEMENT_TYPE_LABELS = {
    StockMovementType.ENTRY: "Entrada",
    StockMovementType.EXIT: "Salida",
    StockMovementType.TRANSFER: "Transferencia",
    StockMovementType.ADJUSTMENT: "Ajuste",
}


def _format_quantity(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class MovementsHistoryDialog(QDialog):
    def __init__(
        self,
        movements: list[StockMovementDTO],
        user_name_resolver: Callable[[int | None], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Movimientos de inventario")
        self.resize(900, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(make_section_title("Movimientos"))

        table = QTableWidget(len(movements), len(_COLUMNS), self)
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, movement in enumerate(movements):
            document = (
                f"{movement.reference_document_type} #{movement.reference_document_id}"
                if movement.reference_document_type and movement.reference_document_id
                else "—"
            )
            values = [
                f"{movement.created_at:%Y-%m-%d}",
                f"{movement.created_at:%H:%M}",
                user_name_resolver(movement.created_by_user_id),
                movement.product_name,
                movement.warehouse_name,
                _MOVEMENT_TYPE_LABELS.get(movement.movement_type, movement.movement_type.value),
                _format_quantity(movement.quantity),
                document,
                movement.reason or "",
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
