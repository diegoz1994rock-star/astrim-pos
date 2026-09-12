"""Diálogo posterior a una venta completada: agradecimiento y pregunta de
impresión de recibo (S/N) con una cuenta regresiva de 10 segundos — si no
responde a tiempo, se descarta sin imprimir.

Ya no muestra un indicador estático de "Caja abierta": la apertura real del
cajón (`SaleViewModel.open_drawer_if_applicable`) ocurre después de este
diálogo y depende del método de pago — mostrar ese texto siempre, sin
importar si el cajón existe o si la venta fue en efectivo, era información
falsa (ver `CashDrawerService`, la única fuente de verdad de si el cajón
realmente se abrió)."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pos.shared_ui.formatting import format_currency

_COUNTDOWN_SECONDS = 10


class PrintReceiptPromptDialog(QDialog):
    def __init__(self, change: Decimal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Venta completada")

        layout = QVBoxLayout(self)

        thanks_label = QLabel("¡Gracias por tu compra!")
        thanks_label.setProperty("emphasis", True)
        layout.addWidget(thanks_label)

        if change > 0:
            layout.addWidget(QLabel(f"Cambio a entregar: {format_currency(change)}"))

        self._question_label = QLabel(self._question_text(_COUNTDOWN_SECONDS))
        layout.addWidget(self._question_label)

        buttons_row = QHBoxLayout()
        yes_button = QPushButton("Sí (S)")
        no_button = QPushButton("No (N)")
        buttons_row.addWidget(yes_button)
        buttons_row.addWidget(no_button)
        layout.addLayout(buttons_row)
        yes_button.clicked.connect(self.accept)
        no_button.clicked.connect(self.reject)

        self._remaining_seconds = _COUNTDOWN_SECONDS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    @staticmethod
    def _question_text(seconds: int) -> str:
        return f"¿Imprimir recibo? (S/N) — se cierra en {seconds}s"

    def _tick(self) -> None:
        self._remaining_seconds -= 1
        if self._remaining_seconds <= 0:
            self.reject()
            return
        self._question_label.setText(self._question_text(self._remaining_seconds))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_S:
            self.accept()
        elif key == Qt.Key.Key_N:
            self.reject()
        else:
            super().keyPressEvent(event)

    def reject(self) -> None:
        self._timer.stop()
        super().reject()

    def accept(self) -> None:
        self._timer.stop()
        super().accept()
