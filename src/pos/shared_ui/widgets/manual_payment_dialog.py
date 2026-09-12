"""Cromado común de los modales de cobro manual (QR, Nequi, Bre-B).

Las tres ventanas deben verse idénticas — mismos colores, tipografía,
botones y tamaño — y solo diferir en el contenido central (imagen QR,
número de Nequi, llave Bre-B). Este widget arma esa parte compartida una
sola vez; cada módulo de pago solo aporta su `central_widget` y su texto.

La referencia mostrada es *provisional* (no el número de factura fiscal,
que solo se genera al completar la venta — ver `billing_service.py`)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pos.shared_ui.formatting import format_currency

_DIALOG_SIZE = (860, 760)


def generate_provisional_reference() -> str:
    """Referencia de venta en curso, no un número de factura real."""
    return f"REF-{uuid.uuid4().hex[:8].upper()}"


class ManualPaymentDialog(QDialog):
    """Base para los modales "Pago mediante QR/Nequi/Bre-B" en Caja.

    Devuelve `Accepted` si el cajero confirma que verificó el pago
    (`Aceptar`) y `Rejected` si cancela — nunca hay confirmación
    automática, el cajero es quien decide.
    """

    def __init__(
        self,
        *,
        title: str,
        total: Decimal,
        customer_name: str,
        central_widget: QWidget,
        caption: str,
        accept_text: str = "Aceptar",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(*_DIALOG_SIZE)
        self.reference = generate_provisional_reference()

        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setProperty("role", "title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        reference_label = QLabel(f"Referencia: {self.reference}")
        reference_label.setProperty("role", "secondary")
        reference_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(reference_label)

        if customer_name:
            customer_label = QLabel(f"Cliente: {customer_name}")
            customer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(customer_label)

        total_label = QLabel(format_currency(total))
        total_label.setProperty("role", "amount")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(total_label)

        central_row = QHBoxLayout()
        central_row.addStretch()
        central_row.addWidget(central_widget)
        central_row.addStretch()
        layout.addLayout(central_row, stretch=1)

        caption_label = QLabel(caption)
        caption_label.setWordWrap(True)
        caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption_label)

        buttons_row = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar", self)
        self.accept_button = QPushButton(accept_text, self)
        buttons_row.addWidget(self.cancel_button)
        buttons_row.addWidget(self.accept_button)
        layout.addLayout(buttons_row)

        self.cancel_button.clicked.connect(self.reject)
        self.accept_button.clicked.connect(self.accept)
