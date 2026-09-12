"""Modelos SQLAlchemy de clientes: datos, créditos/deudas y puntos de fidelidad."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import AuditedEntity, Base, utc_now
from pos.core.database.types import UTCDateTime


class Customer(Base, AuditedEntity):
    """Cliente del negocio."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    document_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    loyalty_points_balance: Mapped[int] = mapped_column(default=0, nullable=False)
    credit_history_cleared_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )
    """Fecha de corte de "Borrar historial" (`CustomerManagementService.
    clear_credit_history`, solo permitido con deuda en cero) — las
    facturas/recibos anteriores a esta fecha se ocultan del historial de
    deuda del cliente, nunca se borran (siguen intactos para Reportes/
    Ganancias/Historial de Ventas)."""


class CreditMovementType(enum.Enum):
    """Tipo de movimiento de crédito/deuda de un cliente."""

    CHARGE = "charge"
    """Cargo: el cliente compra a crédito, aumenta su deuda."""
    PAYMENT = "payment"
    """Abono: el cliente paga parte o toda su deuda."""


class CustomerCreditMovement(Base):
    """Movimiento de crédito/deuda de un cliente. `balance_after` congela el
    saldo resultante para que el historial no dependa de recalcular sumas."""

    __tablename__ = "customer_credit_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    movement_type: Mapped[CreditMovementType] = mapped_column(
        Enum(CreditMovementType, native_enum=False), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """Referencia opcional, ej. el `uuid` de la venta que originó el cargo."""

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class LoyaltyPointsMovementType(enum.Enum):
    """Tipo de movimiento de puntos de fidelidad."""

    EARNED = "earned"
    REDEEMED = "redeemed"


class CustomerLoyaltyPoints(Base):
    """Movimiento de puntos de fidelidad ganados o canjeados por un cliente."""

    __tablename__ = "customer_loyalty_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    points: Mapped[int] = mapped_column(nullable=False)
    movement_type: Mapped[LoyaltyPointsMovementType] = mapped_column(
        Enum(LoyaltyPointsMovementType, native_enum=False), nullable=False
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
