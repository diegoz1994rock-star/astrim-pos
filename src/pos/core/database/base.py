"""Clase base declarativa y mixins de auditoría compartidos por todos los modelos ORM.

Todo modelo de negocio del sistema hereda de `Base` y, salvo excepción
documentada, de `AuditedEntity` (ver DATABASE.md, "Convenciones globales").
"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import UTC, datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from pos.core.database.types import UTCDateTime


class Base(DeclarativeBase):
    """Clase base declarativa única de SQLAlchemy para todo el sistema.

    Todos los módulos registran sus modelos sobre esta misma `MetaData` para
    que Alembic mantenga un único historial de migraciones consistente,
    aunque el código Python de cada módulo permanezca desacoplado
    (ver ARCHITECTURE.md §12b).
    """


def utc_now() -> datetime:
    """Hora actual en UTC, usada como valor por defecto de columnas de auditoría."""
    return datetime.now(UTC)


class UUIDMixin:
    """Columna `uuid` global única.

    La usa el módulo de Sincronización para identificar el mismo registro
    entre estaciones distintas, y sirve como referencia externa estable si
    en el futuro se centraliza en PostgreSQL/MySQL.
    """

    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid_lib.uuid4()),
    )


class TimestampMixin:
    """Columnas de auditoría temporal `created_at` / `updated_at`."""

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class UserStampMixin:
    """Columnas de autoría `created_by_user_id` / `updated_by_user_id`.

    No declaran `ForeignKey` explícita hacia `users` aquí para no forzar el
    orden de creación de tablas entre módulos; la integridad referencial de
    estas columnas se valida en la capa de aplicación, no en el esquema.
    """

    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SoftDeleteMixin:
    """Borrado lógico (`is_deleted` / `deleted_at`) en vez de `DELETE` físico.

    Obligatorio en toda tabla con historial de negocio dependiente (ventas,
    productos, clientes, usuarios, etc.); opcional en catálogos puros sin
    historial dependiente, según se documente en cada modelo.
    """

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class AuditedEntity(UUIDMixin, TimestampMixin, UserStampMixin, SoftDeleteMixin):
    """Combina todos los mixins de auditoría estándar (DATABASE.md, convenciones globales)."""
