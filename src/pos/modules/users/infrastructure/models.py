"""Modelo SQLAlchemy de usuarios del sistema.

`job_area_id`/`job_position_id` referencian `job_areas.id`/`job_positions.id`
por nombre de tabla (string), sin importar el módulo `job_positions`, según
la convención de ARCHITECTURE.md §12b. Es el único modelo organizacional
del sistema (no hay Roles/Permisos): el cargo determina tanto la
clasificación organizacional como el nivel de acceso, vía
`JobPosition.grants_full_access`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import AuditedEntity, Base, TimestampMixin
from pos.core.database.types import UTCDateTime


class User(Base, AuditedEntity):
    """Usuario del sistema, clasificado por Área y Cargo (sin Roles)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    """Hash Argon2id, nunca la contraseña en texto plano (ver core/security)."""

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    emergency_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    """Grupo sanguíneo y factor RH (ej. "O+", "AB-"), texto libre."""
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Ruta al archivo de foto de perfil, copiado bajo el directorio de
    datos de la app (ver `infrastructure/photo_storage.py`)."""

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    job_area_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_areas.id", ondelete="SET NULL"), nullable=True
    )
    job_position_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_positions.id", ondelete="SET NULL"), nullable=True
    )
    """Área y cargo del usuario. El nivel de acceso se deriva del cargo
    (`JobPosition.grants_full_access`), no hay un sistema de permisos
    aparte."""

    documents: Mapped[list[UserDocument]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserDocument(Base, TimestampMixin):
    """Archivo adjunto a un usuario (hoja de vida, documentos, etc.).
    Solo visible/editable desde el formulario de edición de usuario, nunca
    en la tabla de Usuarios. Sin `AuditedEntity`: es un adjunto simple, no
    una entidad de negocio con historial propio — el archivo real vive
    bajo el directorio de datos de la app (ver `infrastructure/document_storage.py`)."""

    __tablename__ = "user_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)

    user: Mapped[User] = relationship(back_populates="documents")
