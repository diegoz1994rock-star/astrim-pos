"""Modelos SQLAlchemy de sesiones activas e intentos de inicio de sesión.

Soportan el requisito de seguridad de bloqueo por múltiples intentos
fallidos (ver ARCHITECTURE.md §8).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, utc_now


class UserSession(Base):
    """Sesión activa de un usuario autenticado."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LoginAttempt(Base):
    """Registro de cada intento de inicio de sesión, exitoso o fallido.

    Es la base para el bloqueo por intentos fallidos: se cuentan los
    intentos con `success=False` en una ventana de tiempo por `username_attempted`.
    """

    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    username_attempted: Mapped[str] = mapped_column(String(60), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
