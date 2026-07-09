"""Modelo SQLAlchemy de usuarios del sistema.

`role_id` referencia `roles.id` por nombre de tabla (string), sin importar
el módulo `roles`, según la convención de ARCHITECTURE.md §12b.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import AuditedEntity, Base


class User(Base, AuditedEntity):
    """Usuario del sistema (administrador, gerente, cajero, mesero,
    cocinero, bodeguero, o rol personalizado)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    """Hash Argon2id, nunca la contraseña en texto plano (ver core/security)."""

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
