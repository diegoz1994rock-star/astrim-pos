"""Modelo SQLAlchemy de configuración de cobro por Nequi."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin


class NequiPaymentConfig(Base, TimestampMixin):
    """Un número de Nequi configurado para mostrarse en Caja.

    Cobro completamente manual: el cajero muestra `number` al cliente y
    confirma visualmente el pago (ver `presentation/nequi_payment_dialog.py`).
    Solo puede haber un número activo a la vez (ver
    `infrastructure/repository.py::NequiPaymentConfigRepository.set_active`).
    """

    __tablename__ = "nequi_payment_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
