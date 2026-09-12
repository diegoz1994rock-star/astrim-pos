"""Ventana grande de cobro por QR estático: muestra el QR configurado en
Administración y espera confirmación manual del cajero.

Mientras el diálogo está abierto la venta permanece sin completar —
`SaleView` solo llama a `complete_sale()` (sin cambios) después de que este
diálogo devuelve `Accepted`, ver `sale_view.py:_open_manual_payment_dialog`."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.shared_ui.widgets.manual_payment_dialog import ManualPaymentDialog

_IMAGE_BOX_SIZE = 560
_CAPTION = (
    "Escanee este código utilizando la aplicación de su banco y digite "
    "manualmente el valor mostrado."
)
_MISSING_MESSAGE = "No hay un QR configurado en Administración → Pagos electrónicos."


class QrPaymentDialog(ManualPaymentDialog):
    """Se abre al elegir el método de pago "QR" en Caja."""

    def __init__(
        self,
        *,
        total: Decimal,
        qr_payment_service: QrPaymentService,
        customer_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        config = qr_payment_service.get_default_config()

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setMinimumSize(_IMAGE_BOX_SIZE, _IMAGE_BOX_SIZE)
        pixmap = QPixmap(config.image_path) if config and config.image_path else QPixmap()
        if not pixmap.isNull():
            image_label.setPixmap(
                pixmap.scaled(
                    _IMAGE_BOX_SIZE,
                    _IMAGE_BOX_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            image_label.setText(_MISSING_MESSAGE)
            image_label.setWordWrap(True)
            image_label.setProperty("role", "danger")

        super().__init__(
            title="Pago mediante QR",
            total=total,
            customer_name=customer_name,
            central_widget=image_label,
            caption=_CAPTION,
            parent=parent,
        )
        if pixmap.isNull():
            self.accept_button.setEnabled(False)
