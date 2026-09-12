"""Modelo SQLAlchemy de configuración de cobro por Bre-B."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin


class BreBPaymentConfig(Base, TimestampMixin):
    """Una llave Bre-B configurada para mostrarse en Caja.

    La llave puede ser un número celular, correo, documento o una llave
    alfanumérica — se almacena tal cual, sin validar el formato. Cobro
    completamente manual: el cajero muestra `key` al cliente y confirma
    visualmente el pago (ver `presentation/breb_payment_dialog.py`).
    """

    __tablename__ = "bre_b_payment_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
