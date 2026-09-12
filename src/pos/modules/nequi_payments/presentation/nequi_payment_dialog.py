"""Ventana grande de cobro por Nequi: muestra el número configurado en
Administración y espera confirmación manual del cajero.

Mientras el diálogo está abierto la venta permanece sin completar —
`SaleView` solo llama a `complete_sale()` después de que este diálogo
devuelve `Accepted`, ver `sale_view.py:_open_manual_payment_dialog`."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.shared_ui.widgets.manual_payment_dialog import ManualPaymentDialog

_CAPTION = "Realice el pago al número anterior y digite el valor indicado."
_MISSING_MESSAGE = "No hay un número de Nequi configurado en Administración → Pagos electrónicos."


class NequiPaymentDialog(ManualPaymentDialog):
    """Se abre al elegir el método de pago "Nequi" en Caja."""

    def __init__(
        self,
        *,
        total: Decimal,
        nequi_payment_service: NequiPaymentService,
        customer_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        config = nequi_payment_service.get_default_config()

        number_label = QLabel(config.number if config is not None else _MISSING_MESSAGE)
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setWordWrap(True)
        number_label.setProperty("role", "hero" if config is not None else "danger")

        super().__init__(
            title="Pago mediante Nequi",
            total=total,
            customer_name=customer_name,
            central_widget=number_label,
            caption=_CAPTION,
            parent=parent,
        )
        if config is None:
            self.accept_button.setEnabled(False)
