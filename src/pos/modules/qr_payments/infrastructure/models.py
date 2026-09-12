"""Modelo SQLAlchemy de configuración de cobro por QR estático."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin


class QrPaymentConfig(Base, TimestampMixin):
    """Un código QR estático configurado para mostrarse en Caja.

    Cobro completamente manual: el cajero muestra `image_path` al cliente
    y confirma visualmente el pago (ver `qr_payments/presentation/
    qr_payment_dialog.py`). Sin campos de API/token/webhook — si en el
    futuro se agrega integración bancaria automática, es un módulo nuevo
    que reemplaza la confirmación manual sin tocar Ventas.
    """

    __tablename__ = "qr_payment_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
