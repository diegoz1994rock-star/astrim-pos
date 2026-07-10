"""Modelos SQLAlchemy de caja: puntos de caja, sesiones (turnos) y movimientos de efectivo."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.cash_register.domain.enums import CashMovementType, CashSessionStatus


class CashRegister(Base, TimestampMixin):
    """Punto de caja físico (puede ser uno solo para negocios pequeños)."""

    __tablename__ = "cash_registers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CashSession(Base):
    """Turno de caja: apertura, cierre y arqueo.

    `expected_amount` es lo que el sistema calcula que debería haber
    (apertura + ventas en efectivo + ingresos manuales - egresos manuales);
    `difference` es `closing_amount - expected_amount`, registrado para
    auditoría del cuadre.
    """

    __tablename__ = "cash_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_register_id: Mapped[int] = mapped_column(ForeignKey("cash_registers.id"), nullable=False)
    status: Mapped[CashSessionStatus] = mapped_column(
        Enum(CashSessionStatus, native_enum=False), default=CashSessionStatus.OPEN, nullable=False
    )
    opened_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    closed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closing_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)


class CashMovement(Base):
    """Movimiento de efectivo dentro de una sesión de caja."""

    __tablename__ = "cash_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id"), nullable=False)
    movement_type: Mapped[CashMovementType] = mapped_column(
        Enum(CashMovementType, native_enum=False), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
