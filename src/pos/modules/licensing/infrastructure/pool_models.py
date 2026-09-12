"""Modelo del pool de códigos de licencia pre-generados — vive en su
propia base de datos SQLite (`licenses_pool.db`), separada de `pos.db`
(ver `pool_db.py`), por eso usa su propia `DeclarativeBase`/`MetaData` en
vez de `pos.core.database.base.Base`: si compartiera la `Base` de negocio,
`create_all()` intentaría crear las ~40 tablas del esquema del cliente
dentro de este archivo, que es solo un catálogo de códigos.

Reutiliza el mismo tipo `UTCDateTime` y el helper `utc_now` que el resto
del sistema (son independientes de qué `MetaData` los use) para mantener
la misma convención de fechas en UTC en toda la app."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from pos.core.database.base import utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.licensing.domain.enums import LicenseType
from pos.modules.licensing.domain.pool_enums import LicensePoolStatus


class PoolBase(DeclarativeBase):
    """`MetaData` propia y exclusiva de `licenses_pool.db` — nunca se
    registra en `pos.core.database.model_registry` (esa es solo para
    `pos.db`)."""

    metadata = MetaData()


class LicensePoolEntry(PoolBase):
    """Un código de licencia pre-generado — su campo `code` es lo único
    que un cliente ve/escribe; el resto lo completa
    `LicenseService.activate()` en el momento de activación. Diseñado
    pensando en las búsquedas que necesitará la futura app Android de
    administración (por código, por empresa, por NIT, por estado)."""

    __tablename__ = "license_pool_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    license_type: Mapped[LicenseType] = mapped_column(
        Enum(LicenseType, native_enum=False), nullable=False
    )
    status: Mapped[LicensePoolStatus] = mapped_column(
        Enum(LicensePoolStatus, native_enum=False),
        default=LicensePoolStatus.AVAILABLE,
        nullable=False,
    )
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_nit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    hardware_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
