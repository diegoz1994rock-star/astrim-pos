"""Ventana grande de cobro por Bre-B: muestra la llave configurada en
Administración y espera confirmación manual del cajero.

Mientras el diálogo está abierto la venta permanece sin completar —
`SaleView` solo llama a `complete_sale()` después de que este diálogo
devuelve `Accepted`, ver `sale_view.py:_open_manual_payment_dialog`."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.shared_ui.widgets.manual_payment_dialog import ManualPaymentDialog

_CAPTION = "Realice la transferencia utilizando la llave mostrada e ingrese el valor indicado."
_MISSING_MESSAGE = "No hay una llave Bre-B configurada en Administración → Pagos electrónicos."


class BreBPaymentDialog(ManualPaymentDialog):
    """Se abre al elegir el método de pago "Bre-B" en Caja."""

    def __init__(
        self,
        *,
        total: Decimal,
        breb_payment_service: BreBPaymentService,
        customer_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        config = breb_payment_service.get_default_config()

        key_label = QLabel(config.key if config is not None else _MISSING_MESSAGE)
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_label.setWordWrap(True)
        key_label.setProperty("role", "hero" if config is not None else "danger")

        super().__init__(
            title="Pago mediante Bre-B",
            total=total,
            customer_name=customer_name,
            central_widget=key_label,
            caption=_CAPTION,
            accept_text="Aceptar pago manualmente",
            parent=parent,
        )
        if config is None:
            self.accept_button.setEnabled(False)
