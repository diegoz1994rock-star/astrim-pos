"""Formulario de abono a una factura — se abre desde `CustomerHistoryDialog`
cuando la factura seleccionada tiene saldo pendiente ("Registrar abono").
Monto y método de pago los captura este diálogo; la persistencia real
(descuento del saldo, ledger de crédito, movimiento de caja, recibo) la
hace `BillingService.register_payment`, llamado por quien abre este
diálogo tras `exec() == Accepted`."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from pos.modules.sales.domain.enums import PaymentMethod
from pos.shared_ui.formatting import format_currency

_PAYMENT_METHOD_LABELS = {
    PaymentMethod.CASH: "Efectivo",
    PaymentMethod.CARD: "Tarjeta",
    PaymentMethod.QR: "QR",
    PaymentMethod.NEQUI: "Nequi",
    PaymentMethod.BRE_B: "Bre-B",
}
"""Mismas opciones no-crédito que puede elegir el cajero en Ventas — un
abono nunca puede pagarse "agregándolo a la deuda"."""


class RegisterPaymentDialog(QDialog):
    def __init__(
        self, *, invoice_number: str, balance_due: Decimal, parent: object = None
    ) -> None:
        super().__init__(parent)
        self._balance_due = balance_due
        self.amount = Decimal(0)
        self.payment_method = PaymentMethod.CASH
        self.note: str | None = None

        self.setWindowTitle(f"Registrar abono — Factura {invoice_number}")

        layout = QFormLayout(self)
        layout.addRow(QLabel(f"Saldo pendiente: {format_currency(balance_due)}"))

        self._amount_edit = QLineEdit(self)
        self._amount_edit.setText(str(balance_due))
        layout.addRow("Monto a abonar", self._amount_edit)

        self._method_combo = QComboBox(self)
        for method, label in _PAYMENT_METHOD_LABELS.items():
            self._method_combo.addItem(label, userData=method)
        layout.addRow("Método de pago", self._method_combo)

        self._note_edit = QLineEdit(self)
        self._note_edit.setPlaceholderText("Opcional")
        layout.addRow("Observación", self._note_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accept(self) -> None:
        try:
            amount = Decimal(self._amount_edit.text())
        except InvalidOperation:
            QMessageBox.warning(self, "Error", "El monto debe ser un número válido.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Error", "El monto debe ser mayor que cero.")
            return
        if amount > self._balance_due:
            QMessageBox.warning(
                self,
                "Error",
                f"El abono ({format_currency(amount)}) no puede ser mayor que el saldo "
                f"pendiente ({format_currency(self._balance_due)}).",
            )
            return
        self.amount = amount
        self.payment_method = self._method_combo.currentData()
        self.note = self._note_edit.text().strip() or None
        self.accept()
