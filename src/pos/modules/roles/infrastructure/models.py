"""Modelos SQLAlchemy de roles y permisos.

Ver DATABASE.md, dominio "Identidad y acceso". `role_permissions` es la
tabla de asociación muchos-a-muchos entre `roles` y `permissions`.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import AuditedEntity, Base, TimestampMixin


class Role(Base, AuditedEntity):
    """Rol de usuario. Incluye los predefinidos por el spec (Administrador
    General, Gerente, Cajero, Mesero, Cocinero, Bodeguero) y cualquier rol
    personalizado creado desde el panel de administración."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system_role: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    """True para los roles predefinidos que el sistema no permite eliminar."""

    permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(Base, TimestampMixin):
    """Permiso granular. `code` sigue la convención `<modulo>.<accion>`
    (ej. `sales.create`, `inventory.adjust`, `reports.export`)."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RolePermission(Base):
    """Asociación rol ↔ permiso."""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id"), nullable=False)

    role: Mapped[Role] = relationship(back_populates="permissions")
